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
_Asistente virtual corporativo de Fanalca._

💡 Pregunta sobre historia, sostenibilidad, negocios o datos de contacto (NIT, correo, teléfono, etc.).  
🧑‍💼 Para **empleo/contratación/vacantes**, te doy los canales oficiales de postulación.
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
llm = ChatOllama(model="gemma3:4b", temperature=temperature)
retriever = FanalcaRetriever("fanalca_knowledge_base_final.json")
structured_tool = FanalcaStructuredTool("structured_data.json")

# ==========================================================
# 🧠 META-PROMPT DEL AGENTE ROUTER
# ==========================================================
ROUTER_PROMPT = """
Eres el Agente Enrutador Inteligente de FANALCA BOT.
Debes decidir cuál herramienta responde:

1) STRUCTURED → Datos concretos (correo, teléfono, NIT, dirección, sedes, redes, horarios, empleo/contratación/vacantes/RRHH).
2) RAG → Información general (historia, proyectos, sostenibilidad, misión, visión, valores).

Responde SOLO con una palabra:
STRUCTURED o RAG
"""

HR_KEYWORDS = [
    "contratación", "contratacion", "contratar", "selección", "seleccion",
    "rrhh", "recursos humanos", "talento", "talento humano",
    "trabaja con nosotros", "trabajar", "empleo", "vacante", "vacantes",
    "oferta laboral", "ofertas laborales", "postular", "postulación", "hoja de vida",
    "hv", "curriculum", "currículum", "cv"
]

BRAND_TERMS = [
    "fanalca", "honda", "fanalvías", "fanalvias", "acopi", "yumbo", "autopartes", "tubos"
]

GREETINGS = [
    "hola", "buenas", "buenos dias", "buenos días", "buenas tardes",
    "buenas noches", "hey", "holi", "saludos"
]

# ==========================================================
# 🔎 UTILIDAD: EXTRAER TEXTO DEL ÚLTIMO MENSAJE DE USUARIO
# (soporta tuple, dict y objetos HumanMessage/AIMessage)
# ==========================================================
def get_last_user_text(messages) -> str:
    for m in reversed(messages):
        # tuple: ("user", "texto")
        if isinstance(m, tuple):
            if len(m) >= 2 and str(m[0]).lower() in ("user", "human"):
                return m[1] if isinstance(m[1], str) else str(m[1])

        # dict: {"role": "user", "content": "texto"}
        if isinstance(m, dict):
            role = (m.get("role") or m.get("type") or "").lower()
            content = m.get("content")
            if role in ("user", "human") and content:
                return content if isinstance(content, str) else str(content)

        # objeto mensaje (LangChain): .type | .role y .content
        role = (getattr(m, "role", None) or getattr(m, "type", None) or "").lower()
        content = getattr(m, "content", None)
        if role in ("user", "human") and content:
            return content if isinstance(content, str) else str(content)

    return ""

# ==========================================================
# 🚦 FUNCIÓN DE ENRUTAMIENTO
# ==========================================================
def route_query(user_query: str) -> str:
    q = user_query.lower().strip()

    # 1) Empleo/contratación → STRUCTURED
    if any(k in q for k in HR_KEYWORDS):
        st.session_state["last_route"] = "STRUCTURED"
        return "STRUCTURED"

    # 2) Datos de contacto → STRUCTURED
    structured_keywords = [
        "correo", "email", "teléfono", "telefono", "dirección", "ubicación",
        "nit", "sede", "horario", "redes", "instagram", "linkedin",
        "facebook", "servicio", "atención", "atencion", "página web", "sitio web", "web"
    ]
    if any(k in q for k in structured_keywords):
        st.session_state["last_route"] = "STRUCTURED"
        return "STRUCTURED"

    # 3) Fallback LLM
    try:
        decision = llm.invoke([
            {"role": "system", "content": ROUTER_PROMPT},
            {"role": "user", "content": user_query}
        ])
        route = str(getattr(decision, "content", "")).strip().upper()
        if route not in {"STRUCTURED", "RAG"}:
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
    # ✔️ Ahora sí obtenemos el texto del usuario, sin importar el tipo de objeto
    last_user_msg = get_last_user_text(state["messages"])
    q_lower = last_user_msg.lower().strip()
    print(f"\n🗣️ Usuario: {q_lower!r}")

    # Respuesta amable a saludos (sin forzar dominio)
    if any(g in q_lower for g in GREETINGS) and "fanalca" not in q_lower:
        return {"messages": [{"role": "assistant", "content": "¡Hola! Soy el asistente de Fanalca S.A. ¿Sobre qué tema de Fanalca te gustaría saber? (historia, misión/visión, unidades de negocio, sostenibilidad, contacto, empleo, etc.)"}]}

    route = route_query(last_user_msg)
    print(f"🚦 Ruta elegida: {route}")

    # Dominio/marca
    has_brand = any(b in q_lower for b in BRAND_TERMS) or ("fanalca" in q_lower)
    has_hr = any(k in q_lower for k in HR_KEYWORDS)

    # 1) Structured primero si aplica
    if route == "STRUCTURED":
        structured_response = structured_tool.get_info(last_user_msg).strip()
        print("✅ Structured Tool →", structured_response)
        if structured_response and "No tengo información" not in structured_response:
            return {"messages": [{"role": "assistant", "content": structured_response}]}
        else:
            print("⚠️ Structured sin coincidencia, pasando a RAG…")
            route = "RAG"

    # 2) Filtro de dominio (bloquea off-topic, pero permite 'Fanalca' o HR+Fanalca)
    if not has_brand and not ("fanalca" in q_lower or (has_hr and "fanalca" in q_lower)):
        return {"messages": [{"role": "assistant", "content": "Lo siento, no tengo información sobre ese tema. Solo puedo responder sobre Fanalca S.A. y sus negocios."}]}

    # 3) RAG
    print("📘 Usando RAG Retriever")
    context = retriever.build_context(last_user_msg, top_k=4)

    if not context.strip():
        return {"messages": [{"role": "assistant", "content": "Lo siento, no tengo información disponible en este momento relacionada con Fanalca."}]}

    system_prompt = f"""
Eres un asistente virtual corporativo experto en Fanalca S.A.
Responde únicamente con la información del CONTEXTO. Si no hay datos suficientes en el contexto para responder con seguridad, di:
"Lo siento, no tengo esa información disponible en este momento porque mi conocimiento se limita a Fanalca."

──────────────── CONTEXTO ────────────────
{context}
──────────────────────────────────────────

Condiciones:
- Mantén un tono claro y profesional.
- No inventes datos ni salgas del dominio Fanalca.
- Si la pregunta es de empleo/contratación y el contexto no trae detalles, orienta brevemente a los canales oficiales (sección 'Trabaja con nosotros' o LinkedIn de Fanalca).
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
    # Intento rápido con Structured si aplica
    route = route_query(user_input)
    if route == "STRUCTURED":
        structured_response = structured_tool.get_info(user_input).strip()
        if structured_response and "No tengo información" not in structured_response:
            st.session_state["last_route"] = "STRUCTURED"
            return structured_response

    # Si no hubo structured, usar grafo (que internamente reintenta router + RAG)
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
