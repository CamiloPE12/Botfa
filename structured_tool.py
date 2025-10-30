# structured_tool.py
import json

HR_KEYWORDS = [
    "contratación", "contratacion", "contratar", "selección", "seleccion",
    "rrhh", "recursos humanos", "talento", "talento humano",
    "trabaja con nosotros", "trabajar", "empleo", "vacante", "vacantes",
    "oferta laboral", "ofertas laborales", "postular", "postulación",
    "hoja de vida", "hv", "curriculum", "currículum", "cv"
]

class FanalcaStructuredTool:
    def __init__(self, data_path="structured_data.json"):
        with open(data_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def _get(self, *keys, default=None):
        cur = self.data
        for k in keys:
            if not isinstance(cur, dict) or k not in cur:
                return default
            cur = cur[k]
        return cur

    def get_info(self, query: str) -> str:
        q = query.lower()

        # ===== EMPLEO / CONTRATACIÓN / RRHH =====
        if any(k in q for k in HR_KEYWORDS):
            empleo = self._get("empleo", default={}) or {}
            # Intentar llaves comunes
            pagina = empleo.get("pagina") or self.data.get("trabaja_con_nosotros") or self.data.get("sitio_web")
            correo_rh = empleo.get("correo") or self.data.get("correo_talento") or self.data.get("correo_contacto")
            plataforma = empleo.get("plataforma") or self._get("redes_sociales", "linkedin") or self.data.get("sitio_web")

            partes = ["🧑‍💼 **Empleo y procesos de contratación en Fanalca**"]
            if pagina:
                partes.append(f"• Postulaciones y procesos: {pagina}")
            if correo_rh:
                partes.append(f"• Contacto de Talento Humano: {correo_rh}")
            if plataforma:
                partes.append(f"• También publicamos vacantes en: {plataforma}")

            if len(partes) > 1:
                return "\n".join(partes)
            else:
                # Fallback seguro
                sitio = self.data.get("sitio_web", "")
                linkedin = self._get("redes_sociales", "linkedin", default="")
                msg = "🧑‍💼 Para empleo y contrataciones, consulta la sección 'Trabaja con nosotros' en nuestros canales oficiales."
                if sitio:
                    msg += f"\n• Sitio oficial: {sitio}"
                if linkedin:
                    msg += f"\n• LinkedIn: {linkedin}"
                return msg

        # ===== CORREOS =====
        if "correo" in q or "email" in q:
            sc = self._get("servicio_cliente", default={}) or {}
            if any(k in q for k in ["cliente", "atención", "atencion", "servicio"]):
                if sc.get("correo"):
                    return f"✉️ El correo de atención al cliente es {sc['correo']}."
            if self.data.get("correo_contacto"):
                return f"✉️ Puedes escribirnos al correo general {self.data['correo_contacto']}."
            return "No tengo información estructurada sobre correos."

        # ===== TELÉFONOS =====
        if "teléfono" in q or "telefono" in q:
            sc = self._get("servicio_cliente", default={}) or {}
            if any(k in q for k in ["cliente", "atención", "atencion", "servicio"]):
                if sc.get("telefono"):
                    return f"📞 El teléfono de atención al cliente de Fanalca es {sc['telefono']}."
            if self.data.get("telefono_principal"):
                return f"📞 El teléfono principal de Fanalca es {self.data['telefono_principal']}."
            return "No tengo información estructurada sobre teléfonos."

        # ===== DIRECCIÓN Y HORARIOS =====
        if "dirección" in q or "direccion" in q or "ubicación" in q or "ubicacion" in q or "sede principal" in q:
            if self.data.get("direccion_principal"):
                return f"📍 La sede principal está en {self.data['direccion_principal']}."
            return "No tengo información estructurada sobre la dirección."
        if "horario" in q:
            if self.data.get("horario_atencion"):
                return f"🕐 Nuestro horario de atención es {self.data['horario_atencion']}."
            return "No tengo información estructurada sobre horarios."

        # ===== DATOS EMPRESARIALES =====
        if "nit" in q:
            if self.data.get("nit"):
                return f"🔢 El NIT de Fanalca S.A. es {self.data['nit']}."
            return "No tengo información estructurada sobre el NIT."
        if "sede" in q or "sedes" in q or "cali" in q:
            sedes = self.data.get("sedes", [])
            if sedes:
                listado = "\n".join([f"- {s.get('ciudad', 'Sede')}: {s.get('direccion', '')}" for s in sedes])
                return f"🏢 Nuestras sedes son:\n{listado}"
            return "No tengo información estructurada sobre sedes."

        # ===== REDES Y WEB =====
        if "redes" in q or "sociales" in q or "instagram" in q or "linkedin" in q or "facebook" in q:
            redes = self.data.get("redes_sociales", {})
            partes = ["🌐 Nuestros canales:"]
            if redes.get("linkedin"):
                partes.append(f"- LinkedIn: {redes['linkedin']}")
            if redes.get("instagram"):
                partes.append(f"- Instagram: {redes['instagram']}")
            if redes.get("facebook"):
                partes.append(f"- Facebook: {redes['facebook']}")
            if len(partes) > 1:
                return "\n".join(partes)
            sitio = self.data.get("sitio_web")
            return f"🌐 Sitio oficial: {sitio}" if sitio else "No tengo información estructurada sobre redes."

        # (✅ Línea corregida: sin coma después de 'q')
        if ("sitio web" in q) or ("página web" in q) or ("pagina web" in q) or ("web" in q):
            sitio = self.data.get("sitio_web")
            return f"🌍 Nuestro sitio web oficial es: {sitio}." if sitio else "No tengo información estructurada sobre el sitio web."

        # ===== SIN COINCIDENCIA =====
        return "No tengo información estructurada sobre esa consulta."
