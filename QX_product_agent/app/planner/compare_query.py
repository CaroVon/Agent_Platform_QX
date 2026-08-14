import time
from app.planner.query_planner import plan_section_queries
from app.rag.rag_pipeline import retrieve_context

def run_comparison(topic, section):
    print("="*60)
    print(f"🔍 评测主题: {topic} | 章节: {section}")
    print("="*60)

    # --- 1. 原始检索路径 (Baseline) ---
    print("\n[路径 A] 原始检索 (直接使用标题)...")
    start_time = time.time()
    raw_query = f"{topic} {section}"
    baseline_context = retrieve_context(raw_query, k=5)
    baseline_time = time.time() - start_time
    
    # --- 2. 规划检索路径 (Query Planning) ---
    print("\n[路径 B] 规划检索 (Query Planning)...")
    start_time = time.time()
    
    # 生成子查询
    sub_queries = plan_section_queries(topic, section, num_queries=3)
    planned_context_list = []
    for q in sub_queries:
        # 每个子查询取 top 2 以保证总量可控
        ctx = retrieve_context(q, k=2)
        planned_context_list.append((q, ctx))
    
    planner_time = time.time() - start_time

    # --- 3. 结果对比可视化 ---
    print("\n" + "#"*20 + " 对比报告 " + "#"*20)
    
    print(f"\n📊 【路径 A: 原始检索】")
    print(f"⏱️  耗时: {baseline_time:.2f}s")
    print(f"📝 检索词: '{raw_query}'")
    print(f"📄 召回内容摘要 (前200字): \n{baseline_context[:200].strip()}...")

    print(f"\n🚀 【路径 B: 规划检索】")
    print(f"⏱️  耗时: {planner_time:.2f}s")
    print(f"📝 拆解子查询:")
    for i, (q, _) in enumerate(planned_context_list, 1):
        print(f"   {i}. {q}")
    
    print(f"📄 召回内容维度统计:")
    for i, (q, ctx) in enumerate(planned_context_list, 1):
        content_len = len(ctx)
        status = "✅ 丰富" if content_len > 100 else "⚠️ 稀疏"
        print(f"   维度 {i} [{status}]: 字符数 {content_len}")

    # --- 核心价值分析 ---
    print("\n" + "="*50)
    print("💡 观察建议:")
    print("1. 覆盖度: 检查 A 是否只停留在表面，而 B 是否触达了技术细节、厂商数据等深层信息。")
    print("2. 相关性: 观察 B 的子查询是否成功避开了宽泛的噪音，命中了更具体的文档块。")
    print("3. 耗时: 规划检索虽然多花了几秒 LLM 生成时间，但换取的是更高质量的数据源。")
    print("="*50)

if __name__ == "__main__":
    # 测试一个比较具体的行研维度，对比效果最明显
    run_comparison("AI眼镜行业", "核心技术路线与传感器方案")