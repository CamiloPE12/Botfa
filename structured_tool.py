# structured_tool.py
import json

class FanalcaStructuredTool:
    def __init__(self, data_path="structured_data.json"):
        with open(data_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def get_info(self, query: str) -> str:
        q = query.lower()

        # --- CORREOS ---
        if "correo" in q or "email" in q:
            if "cliente" in q or "atención" in q or "servicio" in q:
                return f"✉️ El correo de atención al cliente es {self.data['servicio_cliente']['correo']}."
            return f"✉️ Puedes escribirnos al correo general {self.data['correo_contacto']}."

        # --- TELÉFONOS ---
        if "teléfono" in q or "telefono" in q:
            if "cliente" in q or "atención" in q or "servicio" in q:
                return f"📞 El teléfono de atención al cliente de Fanalca es {self.data['servicio_cliente']['telefono']}."
            return f"📞 El teléfono principal de Fanalca es {self.data['telefono_principal']}."

        # --- DIRECCIÓN Y HORARIOS ---
        if "dirección" in q or "ubicación" in q or "sede principal" in q:
            return f"📍 La sede principal está en {self.data['direccion_principal']}."
        if "horario" in q:
            return f"🕐 Nuestro horario de atención es {self.data['horario_atencion']}."

        # --- DATOS EMPRESARIALES ---
        if "nit" in q:
            return f"🔢 El NIT de Fanalca S.A. es {self.data['nit']}."
        if "sede" in q or "sedes" in q or "cali" in q:
            sedes = "\n".join([f"- {s['ciudad']}: {s['direccion']}" for s in self.data["sedes"]])
            return f"🏢 Nuestras sedes son:\n{sedes}"

        # --- REDES Y WEB ---
        if "redes" in q or "sociales" in q or "instagram" in q or "linkedin" in q:
            redes = self.data["redes_sociales"]
            return (
                "🌐 Puedes encontrarnos en:\n"
                f"- LinkedIn: {redes['linkedin']}\n"
                f"- Instagram: {redes['instagram']}\n"
                f"- Facebook: {redes['facebook']}"
            )
        if "sitio web" in q or "página web" in q or "web" in q:
            return f"🌍 Nuestro sitio web oficial es: {self.data['sitio_web']}."

        # --- SIN COINCIDENCIA ---
        return "No tengo información estructurada sobre esa consulta."
