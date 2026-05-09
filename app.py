import gradio as gr
import os
from langsmith import traceable

# Modern Modular Imports
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings, HuggingFaceEndpoint, ChatHuggingFace
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# 1. Setup Data & Vector DB
pdf_files = ["devryze chatbot dataset.pdf", "data5.pdf"]
pages = []
for pdf in pdf_files:
    if os.path.exists(pdf):
        loader = PyPDFLoader(pdf)
        pages.extend(loader.load_and_split())

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vector_db = FAISS.from_documents(pages, embeddings)
retriever = vector_db.as_retriever()

# 2. Modern Prompt
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are the Devryze Agent. Use the context to help. Context: {context}"),
    ("human", "{question}"),
])

# 3. LLM Setup - Updated for 2026 Router Compatibility
repo_id = "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"

llm_base = HuggingFaceEndpoint(
    repo_id=repo_id,
    task="text-generation", # Use text-generation for modern router chat wrapping
    max_new_tokens=512,
    temperature=1.0,
    huggingfacehub_api_token=os.getenv("HUGGINGFACE_TOKEN")
)
llm = ChatHuggingFace(llm=llm_base)

# 4. Construct the Chain (LCEL)
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

chain = (
    RunnablePassthrough.assign(
        context=lambda x: format_docs(retriever.invoke(x["question"]))
    )
    | prompt
    | llm
    | StrOutputParser()
)

# 6. Chat Function with User Isolation
@traceable
def chat(message):
    try:
        response = chain.invoke({"question": message})
        return response
    except Exception as e:
        print(f"Deployment Error: {e}")
        return f"I hit a snag: {str(e)}"

# 7. Simple Chat Interface
iface = gr.Interface(
    fn=chat,
    inputs=[gr.Textbox(label="Message")],
    outputs=gr.Textbox(label="Response"),
    title="Devryze Chatbot",
    description="Chat with the Devryze AI Agent"
)

if __name__ == "__main__":
    iface.launch()