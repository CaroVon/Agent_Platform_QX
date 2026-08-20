"""P1 配置模板。复制为 config.py 并填入真实 key；或直接用环境变量。"""
import os

# ---- Keepa（必选）----
# 环境变量 KEEPA_API_KEY 优先
KEEPA_API_KEY = os.environ.get("KEEPA_API_KEY", "")

# ---- Canopy（可选补充）----
CANOPY_API_KEY = os.environ.get("CANOPY_API_KEY", "")

# ---- 站点 ----
# Keepa domain: 1 = 美亚 amazon.com
DOMAIN = 1
# Canopy marketplace: US
MARKETPLACE = "US"

# ---- 默认参数 ----
DEFAULT_KEYWORD = "yoga mat"      # 方式 A：关键词（用于 ASIN 发现）
DEFAULT_LIMIT = 10                # 拉取前 N 个竞品
DEFAULT_RANGE = 30                # Keepa range: 价格/榜单时间范围（天）
DEFAULT_STATS = 180               # Keepa stats: 返回 90/180 天统计（min/avg/max）

# ---- 输出 ----
OUT_DIR = "outputs"
