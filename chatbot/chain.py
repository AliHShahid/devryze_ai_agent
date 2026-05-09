import os
import re
from urllib.parse import urlparse
from pathlib import Path
from dotenv import load_dotenv
from langsmith import traceable
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings, HuggingFaceEndpoint
from langchain_community.llms import HuggingFacePipeline
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain.text_splitter import RecursiveCharacterTextSplitter


# Load environment from project .env
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

hf_token = os.getenv("HUGGINGFACE_TOKEN")
if not hf_token or hf_token == "hf_your_token_here":
    raise ValueError(
        "HuggingFace API token not configured. Copy .env.example to .env and set HUGGINGFACE_TOKEN."
    )


# 1. Setup Data & Vector DB
ALLOWED_SOURCE_DOMAINS = {"devryze.tech", "linkedin.com", "instagram.com"}

def is_allowed_source(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host in ALLOWED_SOURCE_DOMAINS
    except Exception:
        return False


def clean_context_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", "", text)
    text = re.sub(r"\[email[^\]]*\]", "", text, flags=re.IGNORECASE)
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if re.match(r"^(client|customer|assistant description|faq|frequently asked questions)\b", lowered):
            continue
        if re.match(r"^(user|facilitation)\b", lowered):
            continue
        if re.match(r"^(q:|a:)\b", lowered):
            continue
        if len(stripped) < 3:
            continue
        lines.append(stripped)
    return "\n".join(lines).strip()
text_file = "data.txt"
pages = []
if os.path.exists(text_file):
    try:
        loader = TextLoader(text_file, encoding="utf-8")
        loaded_docs = loader.load()
        for doc in loaded_docs:
            doc.page_content = clean_context_text(doc.page_content)
            if doc.page_content:
                pages.append(doc)
        print(f"Loaded text: {text_file}")
    except Exception as e:
        print(f"Failed to load {text_file}: {e}")

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
index_path = "faiss_index"

if os.path.isdir(index_path):
    vector_db = FAISS.load_local(
        index_path,
        embeddings,
        allow_dangerous_deserialization=True,
    )
    retriever = vector_db.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 4},
    )
elif pages:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=80,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(pages)
    vector_db = FAISS.from_documents(chunks, embeddings)
    vector_db.save_local(index_path)
    retriever = vector_db.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 4},
    )
else:
    vector_db = None
    retriever = None


# 2. Prompt
prompt = PromptTemplate.from_template(
    "You are the Devryze Agent for Devryze.tech.\n"
    "Answer clearly and briefly. Do not repeat the prompt, context, or labels.\n"
    "Do not invent sources, links, or citations. Use only the provided context.\n"
    "If the user greets (hello/hi/hey), respond with a short friendly greeting and ask how you can help.\n"
    "If the user asks what this is, explain Devryze in 1-2 sentences and ask how you can help.\n"
    "Context URLs (if any): {context_urls}\n"
    "Context:\n{context}\n\n"
    "User: {question}\n"
    "Assistant:"
)


# 3. LLM Setup
llm_model = os.getenv("LLM_MODEL", "mistralai/Mistral-7B-Instruct-v0.3")
max_tokens = int(os.getenv("MAX_TOKENS", "128"))
max_tokens = min(max_tokens, 256)
temperature = float(os.getenv("TEMPERATURE", "1.0"))
context_max_chars = int(os.getenv("CONTEXT_MAX_CHARS", "800"))
question_max_chars = int(os.getenv("QUESTION_MAX_CHARS", "500"))
use_local_model = os.getenv("USE_LOCAL_MODEL", "False") == "True"
local_model_name = os.getenv("LOCAL_MODEL", "distilgpt2")

def build_local_llm():
    tokenizer = AutoTokenizer.from_pretrained(local_model_name)
    model = AutoModelForCausalLM.from_pretrained(local_model_name)
    gen = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        max_new_tokens=max_tokens,
        temperature=temperature,
        do_sample=True,
    )
    return HuggingFacePipeline(pipeline=gen)

if use_local_model:
    llm = build_local_llm()
else:
    llm = HuggingFaceEndpoint(
        repo_id=llm_model,
        task="text-generation",
        max_new_tokens=max_tokens,
        temperature=temperature,
        huggingfacehub_api_token=hf_token,
        streaming=True,
    )


# 4. Construct chain
def format_docs(docs):
    text = "\n\n".join(doc.page_content for doc in docs)
    if len(text) > context_max_chars:
        return text[:context_max_chars] + "\n\n[context truncated]"
    return text

if retriever:
    chain = (
        RunnablePassthrough.assign(
            context=lambda x: format_docs(retriever.invoke(x["question"])),
            context_urls=lambda x: "",
        )
        | prompt
        | llm
        | StrOutputParser()
    )
else:
    chain = (
        RunnablePassthrough.assign(context=lambda x: "", context_urls=lambda x: "")
        | prompt
        | llm
        | StrOutputParser()
    )


def extract_sources(text: str) -> list:
    if not text:
        return []
    urls = re.findall(r"https?://[^\s\]\)\}>\"']+", text)
    deduped = []
    seen = set()
    for url in urls:
        if url not in seen and is_allowed_source(url):
            deduped.append(url)
            seen.add(url)
    return deduped


def clean_response(text: str) -> str:
    if text is None:
        return ""
    if not isinstance(text, str):
        try:
            text = str(text)
        except Exception:
            return ""

    for marker in ("Assistant:", "assistant:", "ASSISTANT:"):
        if marker in text:
            text = text.split(marker)[-1]
    for marker in ("User:", "user:", "USER:"):
        if marker in text:
            text = text.split(marker)[0]

    if "Sources:" in text:
        text = text.split("Sources:")[0]

    lines = []
    for line in text.strip().splitlines():
        lowered = line.strip().lower()
        if lowered.startswith("you are the devryze agent"):
            continue
        if lowered.startswith("context:"):
            continue
        if lowered.startswith("document protocol:"):
            continue
        if lowered.startswith("user:"):
            continue
        if lowered.startswith("print sources"):
            continue
        if lowered.startswith("sources:"):
            continue
        if lowered.startswith("assistant description"):
            continue
        if lowered.startswith("customer:"):
            continue
        if lowered.startswith("person:"):
            continue
        if lowered.startswith("assistant:"):
            continue
        if lowered.startswith("user is this response acceptable"):
            continue
        if lowered.startswith("facilitation:"):
            continue
        if lowered.startswith("rewrite the answer"):
            continue
        if lowered.startswith("return only a rewritten answer"):
            continue
        if lowered.startswith("answer:"):
            line = line.split(":", 1)[-1].strip()
            if not line:
                continue
        if re.search(r"\bsources\b", lowered) and re.search(r"https?://", lowered):
            continue
        if "[context truncated]" in lowered:
            line = line.replace("[context truncated]", "").strip()
            if not line:
                continue
        if "http://" in line or "https://" in line:
            continue
        if line.count("/") >= 2 or line.count("|") >= 2:
            continue
        alpha = sum(1 for c in line if c.isalpha())
        if alpha and alpha / max(len(line), 1) < 0.45:
            continue
        letters = [c for c in line if c.isalpha()]
        if letters:
            upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
            if upper_ratio > 0.8 and len(line) > 20:
                continue
        lines.append(line)

    return "\n".join(lines).strip()


def is_low_quality_response(text: str) -> bool:
    if not text:
        return True
    if len(text.strip()) < 25:
        return True
    if text.count("/") >= 2 or text.count("|") >= 2:
        return True
    alpha = sum(1 for c in text if c.isalpha())
    if alpha and alpha / max(len(text), 1) < 0.5:
        return True
    return False


# 5. Chat function
@traceable
def chat(message, user_id: str = "default_user"):
    try:
        safe_message = message[:question_max_chars]
        context = ""
        context_urls = []
        if retriever:
            docs = retriever.invoke(safe_message)
            context = format_docs(docs)
            context_urls = extract_sources(context)

        prompt_text = prompt.format(
            context=context,
            question=safe_message,
            context_urls=", ".join(context_urls),
        )
        response = llm.invoke(prompt_text)
        # Normalize response to a string so the API always returns readable text
        if response is None:
            print("Warning: wrapped_chain returned None for message:", message)
            return "No response from model (check server logs for details)."
        if not isinstance(response, str):
            try:
                response_str = str(response)
            except Exception:
                response_str = "[unserializable response from model]"
            return clean_response(response_str) or response_str
        cleaned = clean_response(response)
        if safe_message.strip().lower() in {"hi", "hello", "hey", "hello there", "hey there"}:
            cleaned = "Hello! How can I help you today?"
        elif is_low_quality_response(cleaned):
            rewrite_prompt = (
                "Return only a rewritten answer in 2-4 sentences. "
                "Do not include sources, labels, or links. If unsure, ask one clarifying question.\n\n"
                f"Answer: {cleaned}"
            )
            rewritten = llm.invoke(rewrite_prompt)
            rewritten_clean = clean_response(rewritten)
            if rewritten_clean and not is_low_quality_response(rewritten_clean):
                cleaned = rewritten_clean
            elif not cleaned:
                cleaned = "Could you clarify what you need help with?"
        return cleaned or response
    except StopIteration:
        print("Chat Error: StopIteration")
        return "I encountered an error: model returned no output. Try again."
    except Exception as e:
        error_text = str(e).strip()
        if not error_text:
            error_text = repr(e)
        print(f"Chat Error: {error_text}")
        return f"I encountered an error: {error_text}"


print("Devryze Chatbot chain loaded")
