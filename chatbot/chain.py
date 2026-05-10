import os
import re
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


# 1. Setup Data & Vector DB (data.txt only)
META_LINE_PREFIXES = (
    "document id",
    "version",
    "last updated",
    "document type",
    "objective",
    "section:",
    "topic:",
    "source_id:",
    "client:",
    "customer:",
    "assistant description",
    "faq",
    "frequently asked questions",
    "user:",
    "facilitation",
    "q:",
    "a:",
)

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "than", "so", "to", "of", "in",
    "on", "for", "with", "at", "by", "from", "is", "are", "was", "were", "be", "been",
    "it", "this", "that", "these", "those", "i", "you", "we", "they", "he", "she",
    "me", "my", "your", "our", "their", "about", "tell", "what", "who", "how", "do",
    "does", "did", "can", "could", "would", "should", "please", "hi", "hello", "hey",
}

ABOUT_DEVRYZE = (
    "Devryze is a specialized engineering and AI solutions company focused on building intelligence "
    "layers for modern enterprises. It helps organizations integrate AI into scalable real-world applications."
)

DEVRYZE_SERVICES = (
    "Devryze provides AI chatbot systems, RAG solutions, workflow automation, machine learning systems, "
    "full-stack web development, mobile applications, data analytics platforms, and enterprise AI architecture consulting."
)

DEVRYZE_CONTACT = (
    "You can reach Devryze via https://devryze.tech/, LinkedIn https://www.linkedin.com/company/pk-devryze/, "
    "Instagram https://www.instagram.com/devryze_pk/, or the contact portal https://www.devryze.tech/#contact."
)


def clean_context_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\[[A-Za-z_ ]+:[^\]]+\]", "", text)
    text = re.sub(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", "", text)
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if lowered.startswith(META_LINE_PREFIXES):
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
    "You are the Devryze support assistant for Devryze.tech.\n"
    "Answer clearly and briefly using only the provided context.\n"
    "If the answer is not in the context, say you do not have that information and ask one clarifying question.\n"
    "Context:\n{context}\n\n"
    "User: {question}\n"
    "Assistant:"
)


# 3. LLM Setup
llm_model = os.getenv("LLM_MODEL", "mistralai/Mistral-7B-Instruct-v0.3")
max_tokens = int(os.getenv("MAX_TOKENS", "128"))
max_tokens = min(max_tokens, 256)
temperature = float(os.getenv("TEMPERATURE", "0.3"))
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
            context=lambda x: format_docs(retriever.invoke(x["question"]))
        )
        | prompt
        | llm
        | StrOutputParser()
    )
else:
    chain = (
        RunnablePassthrough.assign(context=lambda x: "")
        | prompt
        | llm
        | StrOutputParser()
    )


def clean_response(text: str) -> str:
    if text is None:
        return ""
    if not isinstance(text, str):
        try:
            text = str(text)
        except Exception:
            return ""

    text = re.sub(r"\[[A-Za-z_ ]+:[^\]]*\]", "", text)

    for marker in ("Assistant:", "assistant:", "ASSISTANT:"):
        if marker in text:
            text = text.split(marker)[-1]
    for marker in ("User:", "user:", "USER:"):
        if marker in text:
            text = text.split(marker)[0]

    lines = []
    for line in text.strip().splitlines():
        lowered = line.strip().lower()
        if lowered.startswith(META_LINE_PREFIXES):
            continue
        if lowered.startswith("context:"):
            continue
        if lowered.startswith("assistant:"):
            continue
        if lowered.startswith("user:"):
            continue
        lines.append(line.strip())

    return "\n".join(lines).strip()


def is_low_quality_response(text: str) -> bool:
    if not text:
        return True
    if len(text.strip()) < 20:
        return True
    if re.search(r"\b(section|topic|source_id|client)\b", text, flags=re.IGNORECASE):
        return True
    if "[" in text and "]" in text:
        return True
    alpha = sum(1 for c in text if c.isalpha())
    if alpha and alpha / max(len(text), 1) < 0.5:
        return True
    return False


def tokenize(text: str) -> set:
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return {t for t in tokens if len(t) > 2 and t not in STOPWORDS}


def has_context_overlap(question: str, context: str) -> bool:
    q_tokens = tokenize(question)
    if not q_tokens:
        return True
    context_lower = context.lower()
    return any(token in context_lower for token in q_tokens)


def deterministic_response(question: str) -> str | None:
    q = question.strip().lower()
    if re.search(r"\b(what is devryze|who is devryze|tell me about devryze|about devryze)\b", q):
        return ABOUT_DEVRYZE
    if re.search(r"\b(services|service|offer|provide|capabilities|what do you do)\b", q):
        return DEVRYZE_SERVICES
    if re.search(r"\b(contact|reach|email|phone|connect)\b", q):
        return DEVRYZE_CONTACT
    return None


# 5. Chat function
@traceable
def chat(message, user_id: str = "default_user"):
    try:
        safe_message = message[:question_max_chars]
        if safe_message.strip().lower() in {"hi", "hello", "hey", "hello there", "hey there"}:
            return "Hello! How can I help you today?"

        direct = deterministic_response(safe_message)
        if direct:
            return direct

        docs = retriever.invoke(safe_message) if retriever else []
        context = format_docs(docs) if docs else ""
        if not context or not has_context_overlap(safe_message, context):
            return "I do not have that information. What would you like to know about Devryze?"

        prompt_text = prompt.format(
            context=context,
            question=safe_message,
        )
        response = llm.invoke(prompt_text)
        if response is None:
            return "I do not have that information yet. What would you like to know about Devryze?"

        cleaned = clean_response(response)
        if is_low_quality_response(cleaned):
            return "I do not have that information. What would you like to know about Devryze?"
        return cleaned
    except StopIteration:
        return "I encountered an error: model returned no output. Try again."
    except Exception as e:
        error_text = str(e).strip() or repr(e)
        print(f"Chat Error: {error_text}")
        return "I encountered an error. Please try again."


print("Devryze Chatbot chain loaded")
