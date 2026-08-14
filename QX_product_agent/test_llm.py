from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    api_key="EMPTY",
    base_url="http://localhost:8000/v1",
    model="/root/autodl-tmp/models/Qwen/Qwen2.5-7B-Instruct",
    temperature=0.7,
)

response = llm.invoke("请分析AI眼镜行业的竞争格局")

print(response.content)
