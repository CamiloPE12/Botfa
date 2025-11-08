import re
from datetime import datetime, timedelta
import uuid
import streamlit as st
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_ollama import ChatOllama
from dotenv import load_dotenv
from retriever import FanalcaRetriever
from structured_tool import FanalcaStructuredTool

# CONFIGURACIÓN INICIAL
st.set_page_config(page_title="Fanalca Bot", page_icon="fanalca.png", layout="centered")
load_dotenv()

st.image("fanalca.png", width=250)
st.markdown(""" 
_Asistente virtual corporativo de Fanalca._

Pregunta sobre historia, sostenibilidad, negocios o datos de contacto (NIT, correo, teléfono, etc.).  
Para **empleo/contratación/vacantes**, te doy los canales oficiales de postulación.
""")

# CONTROLES AVANZADOS DEL MODELO

st.sidebar.markdown("##  Parámetros del modelo")

# Temperatura (ya incluida)
temperature = st.sidebar.slider(
    "Creatividad del modelo (temperature)",
    0.0, 1.5, 0.7, 0.1,
    help="Valores bajos → respuestas más precisas. Valores altos → más creativas."
)

# Tokens máximos
max_tokens = st.sidebar.slider(
    "Máximo de tokens de salida",
    100, 4096, 1024, 50,
    help="Limita la longitud de la respuesta generada."
)

# Top-p (muestreo nucleus)
top_p = st.sidebar.slider(
    "Top-p (nucleus sampling)",
    0.1, 1.0, 0.9, 0.05,
    help="Controla la diversidad: 1.0 incluye todas las probabilidades; valores bajos hacen las respuestas más seguras."
)

# Penalización por frecuencia (repeticiones)
frequency_penalty = st.sidebar.slider(
    "Penalización por frecuencia",
    0.0, 2.0, 0.0, 0.1,
    help="Aumenta este valor para reducir repeticiones de palabras o frases."
)

# Penalización por presencia (nuevas ideas)
presence_penalty = st.sidebar.slider(
    "Penalización por presencia",
    0.0, 2.0, 0.0, 0.1,
    help="Aumenta este valor para fomentar que el modelo introduzca ideas nuevas."
)

# Penalización de repetición (para Ollama)
repeat_penalty = st.sidebar.slider(
    "Repeat penalty (Ollama)",
    0.5, 2.0, 1.1, 0.1,
    help="Reduce la probabilidad de repetir palabras exactas. 1.0 = sin penalización."
)


#  DEFINICIÓN DEL ESTADO
class State(TypedDict):
    messages: Annotated[list, add_messages]

# CONFIGURACIÓN DEL MODELO Y HERRAMIENTAS
llm = ChatOllama(
    model="gemma3:4b",
    temperature=temperature,
    model_kwargs={
        "top_p": top_p,
        "repeat_penalty": repeat_penalty,
        "num_predict": max_tokens
    }
)

retriever = FanalcaRetriever("fanalca_knowledge_base_final.json")
structured_tool = FanalcaStructuredTool("structured_data.json")

# META-PROMPT DEL AGENTE ROUTER

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

CONTACT_KEYWORDS = [
    "correo", "email", "teléfono", "telefono", "dirección", "direccion", "ubicación", "ubicacion",
    "nit", "sede", "horario", "redes", "instagram", "linkedin", "facebook",
    "servicio", "atención", "atencion", "página web", "pagina web", "web"
]

BRAND_TERMS = [
    "fanalca", "honda", "fanalvías", "fanalvias", "acopi", "yumbo", "autopartes", "tubos"
]

GREETINGS = [
    "hola", "buenas", "buenos dias", "buenos días", "buenas tardes",
    "buenas noches", "hey", "holi", "saludos"
]

FOLLOW_UP_KEYWORDS = [
    "cuentame mas", "cuéntame más", "dime mas", "dime más", "más", "mas",
    "continua", "continúa", "sigue", "amplia", "amplía", "profundiza",
    "detalla", "otro", "ok", "dale", "bien", "listo", "anterior", "eso"
]


#  MEMORIA Y CONTEXTO (SESSION STATE)

if "history" not in st.session_state:
    st.session_state["history"] = []
if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = f"user-{uuid.uuid4().hex[:8]}"
if "last_route" not in st.session_state:
    st.session_state["last_route"] = "—"
if "in_fanalca_context" not in st.session_state:
    st.session_state["in_fanalca_context"] = False
if "last_domain_ts" not in st.session_state:
    st.session_state["last_domain_ts"] = None
if "last_context" not in st.session_state:
    st.session_state["last_context"] = ""
if "last_query" not in st.session_state:
    st.session_state["last_query"] = ""
if "user_profile" not in st.session_state:
    st.session_state["user_profile"] = {"name": None}

def mark_in_domain():
    st.session_state["in_fanalca_context"] = True
    st.session_state["last_domain_ts"] = datetime.now()

def decay_in_domain(minutes: int = 30):
    ts = st.session_state.get("last_domain_ts")
    if ts and datetime.now() - ts > timedelta(minutes=minutes):
        st.session_state["in_fanalca_context"] = False

def is_follow_up(text: str) -> bool:
    t = (text or "").lower().strip()
    if len(t) <= 7 and t in {"más","mas","ok","dale","sigue","continua","bien","listo"}:
        return True
    return any(k in t for k in FOLLOW_UP_KEYWORDS)

# UTILIDAD: EXTRAER TEXTO DEL ÚLTIMO MENSAJE DE USUARIO

def get_last_user_text(messages) -> str:
    for m in reversed(messages):
        if isinstance(m, tuple):
            if len(m) >= 2 and str(m[0]).lower() in ("user", "human"):
                return m[1] if isinstance(m[1], str) else str(m[1])
        if isinstance(m, dict):
            role = (m.get("role") or m.get("type") or "").lower()
            content = m.get("content")
            if role in ("user", "human") and content:
                return content if isinstance(content, str) else str(content)
        role = (getattr(m, "role", None) or getattr(m, "type", None) or "").lower()
        content = getattr(m, "content", None)
        if role in ("user", "human") and content:
            return content if isinstance(content, str) else str(content)
    return ""

# Meta-conversación: nombre del usuario (memoria simple)

ASK_NAME_TRIGGERS = [
    "como me llamo", "cómo me llamo", "sabes como me llamo", "sabes cómo me llamo",
    "sabes mi nombre", "recuerdas mi nombre", "cual es mi nombre", "cuál es mi nombre"
]

def extract_user_name(text: str) -> str | None:
    if not text:
        return None
    patterns = [
        r"(?:\bme llamo\b|\bmi nombre es\b)\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ][\wÁÉÍÓÚÜÑáéíóúüñ.-]*(?:\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][\wÁÉÍÓÚÜÑáéíóúüñ.-]*){0,3})"
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            name = re.split(r"[,.!;:?\n]", name)[0].strip()
            return name[:60]
    return None

def handle_meta(user_text: str) -> str | None:
    name = extract_user_name(user_text)
    if name:
        st.session_state["user_profile"]["name"] = name.title()
        return f"¡Encantado, {name.title()}! Lo tendré presente."
    t = (user_text or "").lower()
    if any(trigger in t for trigger in ASK_NAME_TRIGGERS):
        name = st.session_state["user_profile"].get("name")
        if name:
            return f"Te llamas **{name}**."
        return "Aún no me has dicho tu nombre. Si quieres, dime: “Me llamo …”."
    return None

# FUNCIÓN DE ENRUTAMIENTO
def route_query(user_query: str) -> str:
    decay_in_domain(minutes=30)
    q = (user_query or "").lower().strip()

    # 1) PRIORIDAD ABSOLUTA → HR / CONTACTO
    if any(k in q for k in HR_KEYWORDS) or any(k in q for k in CONTACT_KEYWORDS):
        st.session_state["last_route"] = "STRUCTURED"
        return "STRUCTURED"

    # 2) Seguimiento dentro del dominio → RAG
    if is_follow_up(q) and st.session_state.get("in_fanalca_context"):
        st.session_state["last_route"] = "RAG"
        return "RAG"

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
        print(" Error en router:", e)
        st.session_state["last_route"] = "RAG"
        return "RAG"

# FUNCIÓN PRINCIPAL DEL CHATBOT (Nodo)
def chatbot(state: State):
    decay_in_domain(minutes=30)

    last_user_msg = get_last_user_text(state["messages"])
    q_lower = (last_user_msg or "").lower().strip()
    print(f"\n🗣️ Usuario: {q_lower!r}")

    if any(g in q_lower for g in GREETINGS) and "fanalca" not in q_lower:
        return {"messages": [{"role": "assistant", "content": "¡Hola! Soy el asistente de Fanalca S.A. ¿Sobre qué tema de Fanalca te gustaría saber? (historia, misión/visión, unidades de negocio, sostenibilidad, contacto, empleo, etc.)"}]}

    meta = handle_meta(last_user_msg)
    if meta is not None:
        return {"messages": [{"role": "assistant", "content": meta}]}

    route = route_query(last_user_msg)
    print(f"🚦 Ruta elegida: {route}")

    has_brand = any(b in q_lower for b in BRAND_TERMS) or ("fanalca" in q_lower)
    has_hr = any(k in q_lower for k in HR_KEYWORDS)
    is_continuation = is_follow_up(q_lower)

    # Fallback duro a STRUCTURED si hay términos de RRHH (aunque el router diga RAG)
    if has_hr and route != "STRUCTURED":
        structured_response = structured_tool.get_info(last_user_msg).strip()
        if structured_response and "No tengo información" not in structured_response:
            mark_in_domain()
            return {"messages": [{"role": "assistant", "content": structured_response}]}
        # si no hubo structured útil, seguimos al flujo normal (RAG con dominio)

    # 1) Structured si aplica
    if route == "STRUCTURED":
        structured_response = structured_tool.get_info(last_user_msg).strip()
        print("Structured Tool →", structured_response)
        if structured_response and "No tengo información" not in structured_response:
            mark_in_domain()
            return {"messages": [{"role": "assistant", "content": structured_response}]}
        else:
            print("Structured sin coincidencia, pasando a RAG…")
            route = "RAG"

    # 2) Filtro de dominio (flexible con seguimiento)
    if not (has_brand or st.session_state.get("in_fanalca_context") or ("fanalca" in q_lower) or (has_hr and "fanalca" in q_lower) or is_continuation):
        return {"messages": [{"role": "assistant", "content": "Lo siento, no tengo información sobre ese tema. Solo puedo responder sobre Fanalca S.A. y sus negocios."}]}

    # 3) RAG con "consulta efectiva" y contexto encadenado
    print("Usando RAG Retriever")

    effective_query = last_user_msg
    if is_continuation and not has_brand:
        effective_query = st.session_state.get("last_query") or "Fanalca"

    new_context = retriever.build_context(effective_query, top_k=4)
    prev_context = st.session_state.get("last_context", "").strip()
    if is_continuation and prev_context:
        context = (prev_context + ("\n\n---\n\n" + new_context if new_context.strip() else "")).strip()
    else:
        context = new_context

    if not context.strip():
        return {"messages": [{"role": "assistant", "content": "Lo siento, no tengo información disponible en este momento relacionada con Fanalca."}]}

    follow_up_clause = (
        "- Si la solicitud es de seguimiento (p. ej., \"cuéntame más\", \"continúa\", \"profundiza\"), "
        "amplía el mismo tema usando EXCLUSIVAMENTE el CONTEXTO proporcionado (puedes reorganizar, resumir, destacar puntos adicionales o dar ejemplos derivados del mismo texto), "
        "sin agregar datos externos ni alucinaciones.\n"
    ) if is_continuation else ""

    system_prompt = f"""
Eres un asistente virtual corporativo experto en Fanalca S.A.
Responde únicamente con la información del CONTEXTO. Si no hay datos suficientes en el contexto para responder con seguridad, di:
"Lo siento, no tengo esa información disponible en este momento porque mi conocimiento se limita a Fanalca."
Responde de manera **detallada y extensa**, sin omitir datos relevantes.
Usa toda la información del contexto y produce explicaciones completas y bien estructuradas.

──────────────── CONTEXTO ────────────────
{context}
──────────────────────────────────────────

Condiciones:
- Mantén un tono claro y profesional.
- No inventes datos ni salgas del dominio Fanalca.
- Si la pregunta es de empleo/contratación y el contexto no trae detalles, orienta brevemente a los canales oficiales (sección 'Trabaja con nosotros' o LinkedIn de Fanalca).
{follow_up_clause}
"""
    messages = [{"role": "system", "content": system_prompt}] + state["messages"]
    response = llm.invoke(messages)

    st.session_state["last_context"] = context
    if not (is_continuation and not has_brand):
        st.session_state["last_query"] = last_user_msg
    mark_in_domain()

    return {"messages": [response]}

# GRAFO CONVERSACIONAL
graph_builder = StateGraph(State)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_edge(START, "chatbot")
graph_builder.add_edge("chatbot", END)
memory = MemorySaver()
graph = graph_builder.compile(checkpointer=memory)

# Controles de sesión
if st.sidebar.button("🧹 Nueva conversación"):
    st.session_state["history"] = []
    st.session_state["thread_id"] = f"user-{uuid.uuid4().hex[:8]}"
    st.session_state["in_fanalca_context"] = False
    st.session_state["last_domain_ts"] = None
    st.session_state["last_context"] = ""
    st.session_state["last_query"] = ""
    st.rerun()

# Chat con memoria + meta
def chat_with_memory(user_input: str) -> str:
    meta = handle_meta(user_input)
    if meta is not None:
        st.session_state["last_route"] = "META"
        return meta

    route = route_query(user_input)
    if route == "STRUCTURED":
        structured_response = structured_tool.get_info(user_input).strip()
        if structured_response and "No tengo información" not in structured_response:
            st.session_state["last_route"] = "STRUCTURED"
            mark_in_domain()
            return structured_response

    config = {"configurable": {"thread_id": st.session_state["thread_id"]}}
    result = graph.invoke({"messages": [("user", user_input)]}, config=config)
    last_msg = result["messages"][-1]
    st.session_state["last_route"] = st.session_state.get("last_route", "RAG") or "RAG"

    if isinstance(last_msg, dict) and "content" in last_msg:
        return last_msg["content"]
    if hasattr(last_msg, "content"):
        return last_msg.content
    return str(last_msg)

# INTERFAZ STREAMLIT
st.markdown("---")
st.subheader("Chat con Fanalca Bot")

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

st.sidebar.markdown("### Última ruta usada:")
st.sidebar.write(f"**{st.session_state['last_route']}**")

st.sidebar.markdown("### Perfil recordado")
name = st.session_state["user_profile"].get("name") or "—"
st.sidebar.write(f"Nombre: **{name}**")

with st.sidebar.expander("Historial de conversación"):
    for i, chat in enumerate(st.session_state["history"], 1):
        st.markdown(f"**{i}. Usuario:** {chat['user']}")
        st.markdown(f"** ({chat['route']})** {chat['bot']}")
        st.markdown("---")
