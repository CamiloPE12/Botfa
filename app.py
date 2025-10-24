import streamlit as st
import uuid
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_ollama import ChatOllama
from dotenv import load_dotenv
from retriever import FanalcaRetriever
from structured_tool import FanalcaStructuredTool

# ==========================================================
# ⚙️ CONFIGURACIÓN INICIAL
# ==========================================================
st.set_page_config(page_title="Fanalca Bot", page_icon="🤖", layout="centered")
load_dotenv()

st.markdown("""
# 🤖 Fanalca Bot  
_Asistente virtual corporativo de Fanalca S.A._

💡 Puedes preguntar sobre historia, sostenibilidad, negocios o datos de contacto (NIT, correo, teléfono, etc.).
""")

# ==========================================================
# 🎚️ CONTROL DE TEMPERATURA
# ==========================================================
temperature = st.sidebar.slider(
    "Creatividad del modelo (temperature)",
    0.0, 1.5, 0.7, 0.1,
    help="Valores bajos → respuestas más precisas. Valores altos → más creativas."
)

# ==========================================================
# 🧩 DEFINICIÓN DEL ESTADO
# ==========================================================
class State(TypedDict):
    messages: Annotated[list, add_messages]

# ==========================================================
# 🤖 CONFIGURACIÓN DEL MODELO Y HERRAMIENTAS
# ==========================================================
llm = ChatOllama(model="gemma3:1b", temperature=temperature)
retriever = FanalcaRetriever("fanalca_knowledge_base_final.json")
structured_tool = FanalcaStructuredTool("structured_data.json")

# ==========================================================
# 🧠 META-PROMPT DEL AGENTE ROUTER
# ==========================================================
ROUTER_PROMPT = """
Eres el Agente Enrutador Inteligente de FANALCA BOT.
Debes decidir cuál herramienta responderá la consulta del usuario:

1️⃣ Structured Tool (JSON estructurado) → Datos concretos: correo, teléfono, NIT, dirección, sedes, redes, horarios.
2️⃣ RAG Retriever (base vectorial) → Información general: historia, proyectos, sostenibilidad, misión, visión, valores.

Responde SOLO con una palabra:
STRUCTURED o RAG
"""

# ==========================================================
# 🚦 FUNCIÓN DE ENRUTAMIENTO
# ==========================================================
def route_query(user_query: str) -> str:
    q = user_query.lower().strip()

    # Heurística rápida
    structured_keywords = [
        "correo", "email", "teléfono", "telefono", "dirección", "ubicación",
        "nit", "sede", "horario", "redes", "instagram", "linkedin",
        "facebook", "servicio", "atención"
    ]
    if any(k in q for k in structured_keywords):
        st.session_state["last_route"] = "STRUCTURED"
        return "STRUCTURED"

    # Si no hay coincidencia, usa el modelo para decidir
    try:
        decision = llm.invoke([
            {"role": "system", "content": ROUTER_PROMPT},
            {"role": "user", "content": user_query}
        ])
        route = decision.content.strip().upper()
        if route not in ["STRUCTURED", "RAG"]:
            route = "RAG"
        st.session_state["last_route"] = route
        return route
    except Exception as e:
        print("⚠️ Error en router:", e)
        st.session_state["last_route"] = "RAG"
        return "RAG"

# ==========================================================
# 💬 FUNCIÓN PRINCIPAL DEL CHATBOT
# ==========================================================
def chatbot(state: State):
    last_user_msg = ""
    for m in reversed(state["messages"]):
        if isinstance(m, tuple) and m[0] == "user":
            last_user_msg = m[1]
            break
        if isinstance(m, dict) and m.get("role") == "user":
            last_user_msg = m.get("content", "")
            break

    print(f"\n🗣️ Usuario: {last_user_msg}")

    # Determinar ruta
    route = route_query(last_user_msg)
    print(f"🚦 Ruta elegida: {route}")

    # STRUCTURED → usar JSON
    if route == "STRUCTURED":
        structured_response = structured_tool.get_info(last_user_msg).strip()
        print("✅ Structured Tool →", structured_response)

        if structured_response and "No tengo información" not in structured_response:
            return {"messages": [{"role": "assistant", "content": structured_response}]}
        else:
            print("⚠️ Structured vacío, pasando a RAG...")
            route = "RAG"

    # RAG → usar base vectorial
    print("📘 Usando RAG Retriever")
    context = retriever.build_context(last_user_msg, top_k=4)
    system_prompt = f"""
Eres un asistente virtual experto y confiable especializado exclusivamente en la empresa fanalca

Tu objetivo es responder con precisión, claridad y lenguaje formal, utilizando únicamente la información contenida en el contexto siguiente, que proviene del sitio web oficial de Fanalca y sus fuentes verificadas:

────────────────────────────
{context}
────────────────────────────

💬 Instrucciones importantes:

1. Analiza el contexto con atención. Si el usuario pregunta por elementos como **misión**, **visión**, **valores**, **propósito**, **pilares estratégicos**, **historia**, **unidades de negocio**, **sostenibilidad** o **Fundación Fanalca**, busca términos relacionados en el contexto aunque no estén escritos exactamente igual.
   - Por ejemplo, si el contexto menciona “propósito superior” en lugar de “misión”, explica que ese es el equivalente a la misión corporativa.
   - Si el texto habla de “visión de construcción colectiva”, puedes interpretarlo como la visión institucional.

2. Si la información no aparece en el contexto o no tiene relación con fanalca, responde amablemente:
   👉 “Lo siento, no tengo esa información disponible en este momento porque mi conocimiento se limita a fanalca”

3. No inventes información externa, recetas, chistes o temas que no estén vinculados a fanalca.

4. Responde de manera profesional, clara y con redacción natural, como si fueras un asistente corporativo de fanalca.

5. Si no encuentras la información en el context, responde con:
    "Lo siento, no tengo esa información disponible en este momento."
    """

    messages = [{"role": "system", "content": system_prompt}] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}

# ==========================================================
# 🔗 GRAFO CONVERSACIONAL
# ==========================================================
graph_builder = StateGraph(State)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_edge(START, "chatbot")
graph_builder.add_edge("chatbot", END)
memory = MemorySaver()
graph = graph_builder.compile(checkpointer=memory)

# ==========================================================
# 💬 INTERFAZ STREAMLIT
# ==========================================================
if "history" not in st.session_state:
    st.session_state["history"] = []
if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = f"user-{uuid.uuid4().hex[:8]}"
if "last_route" not in st.session_state:
    st.session_state["last_route"] = "—"

if st.sidebar.button("🧹 Nueva conversación"):
    st.session_state["history"] = []
    st.session_state["thread_id"] = f"user-{uuid.uuid4().hex[:8]}"
    st.rerun()

def chat_with_memory(user_input):
    # Si la consulta es estructurada, responder directamente SIN pasar por el grafo
    route = route_query(user_input)
    if route == "STRUCTURED":
        structured_response = structured_tool.get_info(user_input).strip()
        if structured_response and "No tengo información" not in structured_response:
            st.session_state["last_route"] = "STRUCTURED"
            return structured_response
        else:
            route = "RAG"  # fallback si no hay match

    # Si no fue structured o no hubo dato → usar RAG dentro del grafo
    config = {"configurable": {"thread_id": st.session_state["thread_id"]}}
    result = graph.invoke({"messages": [("user", user_input)]}, config=config)
    last_msg = result["messages"][-1]

    st.session_state["last_route"] = "RAG"

    if isinstance(last_msg, dict) and "content" in last_msg:
        return last_msg["content"]
    if hasattr(last_msg, "content"):
        return last_msg.content
    return str(last_msg)


st.markdown("---")
st.subheader("💬 Chat con Fanalca Bot")

user_input = st.chat_input("Escribe tu pregunta aquí...")

if user_input:
    with st.spinner("Pensando..."):
        response = chat_with_memory(user_input)
        route = st.session_state.get("last_route", "RAG")
        st.session_state["history"].append({"user": user_input, "bot": response, "route": route})

for chat in st.session_state["history"]:
    with st.chat_message("user"):
        st.markdown(chat["user"])
    with st.chat_message("assistant"):
        st.markdown(f"**[{chat['route']}]** {chat['bot']}")

st.sidebar.markdown("### 🧭 Última ruta usada:")
st.sidebar.write(f"**{st.session_state['last_route']}**")

with st.sidebar.expander("📜 Historial de conversación"):
    for i, chat in enumerate(st.session_state["history"], 1):
        st.markdown(f"**{i}. Usuario:** {chat['user']}")
        st.markdown(f"**🤖 ({chat['route']})** {chat['bot']}")
        st.markdown("---")
