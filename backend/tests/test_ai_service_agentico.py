"""Tests del modo agéntico (fase 1) de ai_service.py: el bucle de
tool-calling contra Gemini y contra un proveedor OpenAI-compatible (Groq),
con httpx simulado -nunca se llama a un proveedor real en los tests."""

import json

import httpx
import pytest

import app.services.ai_service as ai_service
from app.services.ai_service import AiServiceError, preguntar_agentico


class _FakeQueryVacia:
    def options(self, *a, **k):
        return self

    def filter(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def all(self):
        return []


class FakeDB:
    """Sin datos: estos tests prueban el BUCLE agéntico (cuántas rondas,
    qué se le pasa al modelo), no el contenido real de cada herramienta
    -eso ya lo cubre test_ai_tools.py."""

    def query(self, model):
        return _FakeQueryVacia()


class FakeConfig:
    def __init__(self, provider="gemini", api_key="clave", chat_model="modelo-x", agentic_enabled=True):
        self.provider = provider
        self.api_key = api_key
        self.chat_model = chat_model
        self.agentic_enabled = agentic_enabled
        self.embedding_api_key = "clave-jina"


class FakeResponse:
    def __init__(self, json_data):
        self.status_code = 200
        self._json_data = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json_data


def _secuencia_post(respuestas):
    """httpx.post devuelve, en orden, cada dict de `respuestas` -una por
    cada ronda del bucle agéntico."""
    it = iter(respuestas)

    def _post(url, **k):
        return FakeResponse(next(it))

    return _post


def test_proveedor_no_soportado_rechaza_antes_de_llamar_a_nadie(monkeypatch):
    def _falla(*a, **k):
        raise AssertionError("no debería llamar a ningún proveedor")

    monkeypatch.setattr(httpx, "post", _falla)
    with pytest.raises(AiServiceError, match="modo agéntico"):
        preguntar_agentico(db=FakeDB(), config=FakeConfig(provider="ollama_cloud"), pregunta="hola")


# --- Gemini -----------------------------------------------------------------

def _gemini_texto(texto):
    return {"candidates": [{"content": {"parts": [{"text": texto}]}}]}


def _gemini_tool_call(nombre, args):
    return {"candidates": [{"content": {"parts": [{"functionCall": {"name": nombre, "args": args}}]}}]}


def test_gemini_llama_una_herramienta_y_despues_responde(monkeypatch):
    respuestas = [
        _gemini_tool_call("ver_estado_aplicacion", {}),
        _gemini_texto("No hay cambios pendientes, todo está aplicado."),
    ]
    monkeypatch.setattr(httpx, "post", _secuencia_post(respuestas))

    resultado = preguntar_agentico(db=FakeDB(), config=FakeConfig(provider="gemini"), pregunta="¿hay cambios sin aplicar?")
    assert resultado["respuesta"] == "No hay cambios pendientes, todo está aplicado."
    assert resultado["herramientas_usadas"] == ["ver_estado_aplicacion"]
    assert resultado["propuesta"] is None


def test_gemini_una_propuesta_se_captura_sin_ejecutarse(monkeypatch):
    respuestas = [
        _gemini_tool_call("proponer_crear_acl", {"name": "redes_sociales", "type": "dstdomain", "value": ".facebook.com"}),
        _gemini_texto("Te propongo crear la ACL 'redes_sociales'. Revisala y confirmala en el panel."),
    ]
    monkeypatch.setattr(httpx, "post", _secuencia_post(respuestas))

    resultado = preguntar_agentico(db=FakeDB(), config=FakeConfig(provider="gemini"), pregunta="creá una ACL para facebook")
    assert resultado["propuesta"] == {
        "accion": "proponer_crear_acl",
        "argumentos": {"name": "redes_sociales", "type": "dstdomain", "value": ".facebook.com"},
    }
    assert "proponer_crear_acl" in resultado["herramientas_usadas"]


def test_gemini_responde_texto_directo_sin_herramientas(monkeypatch):
    monkeypatch.setattr(httpx, "post", _secuencia_post([_gemini_texto("Hola, ¿en qué te ayudo?")]))
    resultado = preguntar_agentico(db=FakeDB(), config=FakeConfig(provider="gemini"), pregunta="hola")
    assert resultado["respuesta"] == "Hola, ¿en qué te ayudo?"
    assert resultado["herramientas_usadas"] == []


def test_gemini_agota_iteraciones_sin_texto_final(monkeypatch):
    # Siempre pide la misma herramienta, nunca da una respuesta de texto.
    monkeypatch.setattr(
        httpx, "post",
        _secuencia_post([_gemini_tool_call("ver_estado_aplicacion", {})] * 10),
    )
    with pytest.raises(AiServiceError, match="varios pasos"):
        preguntar_agentico(db=FakeDB(), config=FakeConfig(provider="gemini"), pregunta="algo")


# --- OpenAI-compatible (Groq/NVIDIA) -----------------------------------------

def _openai_texto(texto):
    return {"choices": [{"message": {"role": "assistant", "content": texto}}]}


def _openai_tool_call(call_id, nombre, args):
    return {
        "choices": [{
            "message": {
                "role": "assistant", "content": None,
                "tool_calls": [{"id": call_id, "function": {"name": nombre, "arguments": json.dumps(args)}}],
            },
        }],
    }


def test_groq_llama_una_herramienta_y_despues_responde(monkeypatch):
    respuestas = [
        _openai_tool_call("call_1", "listar_acls", {}),
        _openai_texto("Tenés 3 ACLs configuradas."),
    ]
    monkeypatch.setattr(httpx, "post", _secuencia_post(respuestas))

    resultado = preguntar_agentico(db=FakeDB(), config=FakeConfig(provider="groq"), pregunta="¿cuántas ACLs tengo?")
    assert resultado["respuesta"] == "Tenés 3 ACLs configuradas."
    assert resultado["herramientas_usadas"] == ["listar_acls"]


def test_groq_argumentos_json_invalidos_no_revienta(monkeypatch):
    """La API del proveedor podría (en teoría, con un modelo gratuito que
    alucina) mandar 'arguments' que no es JSON válido -no debe tirar
    abajo la conversación."""
    malformado = {
        "choices": [{
            "message": {
                "role": "assistant", "content": None,
                "tool_calls": [{"id": "call_1", "function": {"name": "listar_acls", "arguments": "{esto no es json"}}],
            },
        }],
    }
    monkeypatch.setattr(httpx, "post", _secuencia_post([malformado, _openai_texto("Listo.")]))
    resultado = preguntar_agentico(db=FakeDB(), config=FakeConfig(provider="groq"), pregunta="algo")
    assert resultado["respuesta"] == "Listo."


# --- Fallos reales encontrados en revisión de código -----------------------

def test_error_de_una_herramienta_no_tumba_la_conversacion(monkeypatch):
    """Antes de este fix, un fallo real de una herramienta (Jina AI caído en
    buscar_documentacion, un error de base de datos) propagaba y reventaba
    toda la conversación en vez de devolverse como parte del resultado de
    esa llamada, para que el modelo pueda seguir."""
    import app.services.ai_tools as ai_tools

    def _falla(db, config, nombre, argumentos):
        raise AiServiceError("Jina AI no está disponible en este momento (503).")

    monkeypatch.setattr(ai_tools, "ejecutar_herramienta", _falla)
    respuestas = [
        _gemini_tool_call("buscar_documentacion", {"pregunta": "algo"}),
        _gemini_texto("No pude buscar en la documentación en este momento."),
    ]
    monkeypatch.setattr(httpx, "post", _secuencia_post(respuestas))

    resultado = preguntar_agentico(db=FakeDB(), config=FakeConfig(provider="gemini"), pregunta="algo")
    assert resultado["respuesta"] == "No pude buscar en la documentación en este momento."


def test_propuesta_no_se_pierde_si_se_agotan_las_iteraciones(monkeypatch):
    """Antes de este fix, si el modelo armaba una propuesta y después seguía
    pidiendo herramientas sin nunca dar una respuesta de texto final, la
    propuesta ya armada se perdía -el admin solo veía un error genérico."""
    respuestas = [
        _gemini_tool_call("proponer_crear_acl", {"name": "redes_sociales", "type": "dstdomain", "value": ".facebook.com"}),
    ] + [_gemini_tool_call("ver_estado_aplicacion", {})] * 5  # nunca da texto final
    monkeypatch.setattr(httpx, "post", _secuencia_post(respuestas))

    resultado = preguntar_agentico(db=FakeDB(), config=FakeConfig(provider="gemini"), pregunta="creá una ACL")
    assert resultado["propuesta"] == {
        "accion": "proponer_crear_acl",
        "argumentos": {"name": "redes_sociales", "type": "dstdomain", "value": ".facebook.com"},
    }
    assert "revisala antes de confirmarla" in resultado["respuesta"]
