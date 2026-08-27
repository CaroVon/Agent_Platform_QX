//! qx-svg-tools —— PPT SVG 页面处理 Rust 内核（P1）。
//!
//! 与 Python 侧（svg_author/sanitize + cross_page.snap_font_sizes +
//! svg_qa 元素/色板/字号检查）产物等价，PyO3 进程内直调。
//! 等价性由 agents/tests/test_svg_qa.py 的双实现对照测试保障。

use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use regex::Regex;
use once_cell::sync::Lazy;
use std::collections::HashSet;

/// 与 svg_author._BANNED_TEXT_ATTRS 一致
const BANNED_ATTRS: &[&str] = &[
    "dx", "dy", "alignment-baseline", "direction", "dominant-baseline",
    "font-kerning", "font-feature-settings", "font-size-adjust", "font-stretch",
    "font-synthesis", "font-variant", "font-variation-settings", "font",
    "hyphens", "kerning", "line-height", "overflow-wrap", "text-align",
    "text-align-last", "text-indent", "text-rendering", "text-shadow",
    "text-transform", "unicode-bidi", "vertical-align", "white-space",
    "word-spacing", "word-break", "writing-mode", "baseline-shift",
    "lengthAdjust", "textLength", "startOffset", "style",
];

/// 与 cross_page.ALLOWED_FONT_SIZES 一致（19 档）
const ALLOWED_SIZES: &[i64] = &[
    9, 10, 11, 12, 13, 14, 15, 16, 18, 20, 22, 26, 28, 32, 36, 44, 56, 68, 80,
];

static RE_ATTR: Lazy<Regex> = Lazy::new(|| Regex::new(r#"\s([A-Za-z_-]+)="([^"]*)""#).unwrap());
static RE_FONT_SIZE: Lazy<Regex> = Lazy::new(|| Regex::new(r#"font-size="([\d.]+)""#).unwrap());
static RE_EL: Lazy<Regex> = Lazy::new(|| Regex::new(r#"<(ns\d+:)?([a-zA-Z]+)\b"#).unwrap());
static RE_COLOR: Lazy<Regex> =
    Lazy::new(|| Regex::new(r#"(?:fill|stroke)="(#[0-9A-Fa-f]{3,8})""#).unwrap());

fn hex_to_rgb(v: &str) -> Option<(i64, i64, i64)> {
    let h = v.trim_start_matches('#');
    let h = if h.len() == 8 { &h[..6] } else { h };
    if h.len() != 3 && h.len() != 6 {
        return None;
    }
    let full: String = if h.len() == 3 {
        h.chars().flat_map(|c| [c, c]).collect()
    } else {
        h.to_string()
    };
    let r = i64::from_str_radix(&full[0..2], 16).ok()?;
    let g = i64::from_str_radix(&full[2..4], 16).ok()?;
    let b = i64::from_str_radix(&full[4..6], 16).ok()?;
    Some((r, g, b))
}

fn nearest_allowed(size: f64) -> i64 {
    // 与 cross_page.snap_font_sizes 的就近档 snapping 一致
    let mut best = ALLOWED_SIZES[0];
    let mut best_d = f64::INFINITY;
    for &s in ALLOWED_SIZES {
        let d = (s as f64 - size).abs();
        if d < best_d {
            best_d = d;
            best = s;
        }
    }
    best
}

/// sanitize：剔除禁用属性（等价 svg_author.sanitize_svg 的属性黑名单部分；
/// Python 版另有原生图表标记剥离，创作链已在 Rust 前置层之外保留）。
#[pyfunction]
pub fn sanitize(svg: &str) -> PyResult<String> {
    let mut out = String::with_capacity(svg.len());
    let mut last = 0usize;
    for m in RE_ATTR.captures_iter(svg) {
        let whole = m.get(0).unwrap();
        let name = m.get(1).unwrap().as_str();
        if BANNED_ATTRS.contains(&name) {
            out.push_str(&svg[last..whole.start()]);
            last = whole.end();
        }
    }
    out.push_str(&svg[last..]);
    Ok(out)
}

/// snap_font_sizes：字号就近收敛到白名单档。
/// 返回 (svg, snapped_count)。Python 版返回详细 info——高频路径只需要计数。
#[pyfunction]
pub fn snap_font_sizes(svg: &str) -> PyResult<(String, usize)> {
    // 语义对齐 Python：截断为整数，整数命中白名单则保留原字符串
    let allowed: HashSet<i64> = ALLOWED_SIZES.iter().copied().collect();
    let mut snapped = 0usize;
    let out = RE_FONT_SIZE
        .replace_all(svg, |caps: &regex::Captures| {
            let raw = caps[1].parse::<f64>().unwrap_or(0.0);
            let n_int = raw.trunc() as i64;
            if allowed.contains(&n_int) {
                return caps[0].to_string();
            }
            let target = nearest_allowed(n_int as f64);
            snapped += 1;
            format!("font-size=\"{}\"", target)
        })
        .into_owned();
    Ok((out, snapped))
}

fn count_elements(svg: &str, names: &[&str]) -> usize {
    let want: HashSet<&str> = names.iter().copied().collect();
    RE_EL
        .captures_iter(svg)
        .filter(|c| want.contains(&c[2]))
        .count()
}

fn near_any(c: (i64, i64, i64), allowed: &[(i64, i64, i64)], tol: i64) -> bool {
    allowed.iter().any(|a| {
        (c.0 - a.0).abs() <= tol && (c.1 - a.1).abs() <= tol && (c.2 - a.2).abs() <= tol
    })
}

/// qa_element_budget：信息密度检查（svg_qa 第 2 项核心子集）。
/// 返回 issues 列表（与 Python 版文案对齐）。
#[pyfunction]
pub fn qa_element_budget(svg: &str, page_type: &str) -> Vec<String> {
    let mut issues = Vec::new();
    let is_cover = page_type == "cover" || page_type == "conclusion";
    if is_cover {
        return issues;
    }
    let n_text = count_elements(svg, &["text"]);
    let n_rect = count_elements(svg, &["rect"]);
    let n_shape = count_elements(svg, &["circle", "ellipse", "path", "polygon"]);
    let has_defs = svg.contains("<defs") || svg.contains("linearGradient");
    if n_text < 8 {
        issues.push(format!(
            "信息密度不足：<text> 仅 {} 个（参考基线≥35，下限 8）",
            n_text
        ));
    }
    if n_rect < 4 && n_shape < 6 {
        issues.push(format!(
            "视觉结构不足：rect {} / 图形 {}（参考基线 rect≥14）",
            n_rect, n_shape
        ));
    }
    if !has_defs && n_rect + n_shape < 12 {
        issues.push("缺少视觉层次（无 defs/渐变且图形元素过少）".to_string());
    }
    issues
}

/// qa_palette：色板纪律（越板色值清单，svg_qa 第 3 项核心子集）。
#[pyfunction]
pub fn qa_palette(svg: &str, palette_hex: Vec<String>) -> Vec<String> {
    let mut allowed: Vec<(i64, i64, i64)> = vec![(248, 250, 252), (255, 255, 255),
        (15, 23, 42), (100, 116, 139), (79, 70, 229), (99, 102, 241)];
    for h in &palette_hex {
        if let Some(rgb) = hex_to_rgb(h) {
            allowed.push(rgb);
        }
    }
    let mut off: Vec<String> = Vec::new();
    let mut seen = HashSet::new();
    for cap in RE_COLOR.captures_iter(svg) {
        let hx = cap[1].to_string();
        if !seen.insert(hx.clone()) {
            continue;
        }
        if let Some(rgb) = hex_to_rgb(&hx) {
            let neutral = rgb.0.max(rgb.1).max(rgb.2) - rgb.0.min(rgb.1).min(rgb.2) <= 24;
            if !neutral && !near_any(rgb, &allowed, 52) {
                off.push(hx);
            }
        }
    }
    if !off.is_empty() {
        let sample: Vec<String> = off.iter().take(3).cloned().collect();
        issues_palette(off.len(), sample)
    } else {
        Vec::new()
    }
}

fn issues_palette(n: usize, sample: Vec<String>) -> Vec<String> {
    vec![format!(
        "色板纪律：{} 个色值偏离主题（如 {:?}）",
        n, sample
    )]
}

/// qa_font_sizes：字号越档清单（svg_qa 第 4 项）。
#[pyfunction]
pub fn qa_font_sizes(svg: &str) -> Vec<String> {
    let allowed: HashSet<i64> = ALLOWED_SIZES.iter().copied().collect();
    let mut bad: Vec<i64> = Vec::new();
    let mut seen = HashSet::new();
    for cap in RE_FONT_SIZE.captures_iter(svg) {
        if let Ok(v) = cap[1].parse::<i64>() {
            if !allowed.contains(&v) && seen.insert(v) {
                bad.push(v);
            }
        }
    }
    if bad.is_empty() {
        Vec::new()
    } else {
        bad.sort();
        vec![format!("字号越档：{:?}", bad.iter().take(5).collect::<Vec<_>>())]
    }
}

/// batch：一次调用跑齐 sanitize → snap → qa（创作链每页一次往返）。
#[pyfunction]
pub fn process_page(
    svg: &str,
    page_type: &str,
    palette_hex: Vec<String>,
) -> PyResult<PyObject> {
    Python::with_gil(|py| {
        let sanitized = sanitize(svg)?;
        let (snapped, snap_count) = snap_font_sizes(&sanitized)?;
        let mut issues = qa_element_budget(&snapped, page_type);
        issues.extend(qa_palette(&snapped, palette_hex));
        issues.extend(qa_font_sizes(&snapped));
        let dict = PyDict::new(py);
        dict.set_item("svg", snapped).map_err(PyErr::from)?;
        dict.set_item("snap_count", snap_count).map_err(PyErr::from)?;
        dict.set_item("issues", issues).map_err(PyErr::from)?;
        Ok(dict.into())
    })
}

#[pymodule]
fn qx_svg_tools(py: Python, m: &Bound<PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(sanitize, m)?)?;
    m.add_function(wrap_pyfunction!(snap_font_sizes, m)?)?;
    m.add_function(wrap_pyfunction!(qa_element_budget, m)?)?;
    m.add_function(wrap_pyfunction!(qa_palette, m)?)?;
    m.add_function(wrap_pyfunction!(qa_font_sizes, m)?)?;
    m.add_function(wrap_pyfunction!(process_page, m)?)?;
    m.add("ALLOWED_FONT_SIZES", ALLOWED_SIZES.to_vec())
        .map_err(|_| PyRuntimeError::new_err("const"))?;
    Ok(())
}
