from langchain_openai import ChatOpenAI

def get_llm_local():

    llm = ChatOpenAI(
        api_key="EMPTY",
        base_url="http://localhost:8000/v1",
        model="/root/autodl-tmp/models/Qwen/Qwen2.5-7B-Instruct",
        temperature=0.7,
    )

    return llm

# 建议修改为支持不同 provider 的结构
def get_llm(model_name="deepseek-chat"):
    return ChatOpenAI(
        api_key=os.getenv("API_KEY"),
        base_url=os.getenv("BASE_URL"), 
        model=model_name,
        temperature=0.3 # 研报需要更高稳定性，建议降低 temperature
    )
    