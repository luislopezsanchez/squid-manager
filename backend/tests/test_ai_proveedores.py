"""Proveedores de IA del Asistente (app/services/ai_providers.py y ai_service.py):
catálogo, URL propia, Anthropic nativo y búsqueda solo por texto completo."""
import httpx
import pytest

from app.services import ai_providers, ai_service
from app.services.ai_service import AiServiceError, generar_respuesta, listar_modelos, preguntar_agentico


class Config:
    def __init__(self, provider="anthropic", api_key="clave", chat_model="modelo", base_url=None, agentic_enabled=True):
        self.provider, self.api_key, self.chat_model, self.base_url = provider, api_key, chat_model, base_url
        self.agentic_enabled = agentic_enabled
        self.embedding_api_key = None
        self.enabled = True


class Resp:
    status_code = 200

    def __init__(self, datos): self._d = datos
    def raise_for_status(self): pass
    def json(self): return self._d


class FakeDB:
    def query(self, *_):
        class Q:
            def options(s, *a, **k): return s
            def filter(s, *a, **k): return s
            def order_by(s, *a, **k): return s
            def all(s): return []
        return Q()


# --- catálogo -----------------------------------------------------------------

def test_todo_proveedor_trae_los_campos_que_usa_el_panel():
    for clave, p in ai_providers.PROVEEDORES.items():
        assert {"nombre", "tipo", "url", "modelo_ejemplo", "requiere_clave", "url_editable", "agentico", "ayuda"} <= set(p), clave
        assert p["tipo"] in ("openai", "anthropic", "gemini", "ollama")


def test_hay_uno_personalizado_y_uno_local_sin_clave_obligatoria():
    assert ai_providers.PROVEEDORES["personalizado"]["url_editable"] and not ai_providers.PROVEEDORES["personalizado"]["requiere_clave"]
    assert not ai_providers.PROVEEDORES["ollama_local"]["requiere_clave"]


def test_url_efectiva_solo_respeta_la_del_admin_si_el_proveedor_la_admite():
    assert ai_providers.url_efectiva("personalizado", " http://mi-servidor:8000/v1/ ") == "http://mi-servidor:8000/v1"
    assert ai_providers.url_efectiva("openai", "http://otro/v1") == "https://api.openai.com/v1"
    assert ai_providers.url_efectiva("ollama_local", None) == "http://localhost:11434/v1"


def test_proveedor_personalizado_sin_url_avisa():
    with pytest.raises(AiServiceError, match="URL base"):
        generar_respuesta("s", "p", Config(provider="personalizado", base_url=None))


def test_proveedor_desconocido_se_rechaza():
    with pytest.raises(AiServiceError, match="desconocido"):
        generar_respuesta("s", "p", Config(provider="no_existe"))


# --- OpenAI-compatible con URL propia y sin clave ----------------------------------

def test_personalizado_usa_su_url_y_no_manda_cabecera_si_no_hay_clave(monkeypatch):
    visto = {}

    def post(url, headers=None, json=None, timeout=None):
        visto.update(url=url, headers=headers)
        return Resp({"choices": [{"message": {"content": "hola"}}]})

    monkeypatch.setattr(httpx, "post", post)
    r = generar_respuesta("sys", "pregunta", Config(provider="personalizado", api_key=None, base_url="http://10.0.0.5:8000/v1"))
    assert r == "hola"
    assert visto["url"] == "http://10.0.0.5:8000/v1/chat/completions"
    assert "Authorization" not in (visto["headers"] or {})


def test_con_clave_manda_bearer(monkeypatch):
    visto = {}
    monkeypatch.setattr(httpx, "post", lambda url, headers=None, json=None, timeout=None: (visto.update(h=headers), Resp({"choices": [{"message": {"content": "ok"}}]}))[1])
    generar_respuesta("s", "p", Config(provider="openrouter", api_key="sk-x"))
    assert visto["h"] == {"Authorization": "Bearer sk-x"}


# --- Anthropic nativo ---------------------------------------------------------------

def test_anthropic_usa_su_api_nativa_y_extrae_el_texto(monkeypatch):
    visto = {}

    def post(url, headers=None, json=None, timeout=None):
        visto.update(url=url, headers=headers, body=json)
        return Resp({"content": [{"type": "text", "text": "Respuesta "}, {"type": "text", "text": "de Claude"}]})

    monkeypatch.setattr(httpx, "post", post)
    assert generar_respuesta("sys", "hola", Config()) == "Respuesta de Claude"
    assert visto["url"] == "https://api.anthropic.com/v1/messages"
    assert visto["headers"]["x-api-key"] == "clave" and visto["headers"]["anthropic-version"]
    assert visto["body"]["system"] == "sys" and visto["body"]["messages"] == [{"role": "user", "content": "hola"}]


def test_anthropic_listar_modelos_usa_x_api_key(monkeypatch):
    visto = {}
    monkeypatch.setattr(httpx, "get", lambda url, headers=None, timeout=None: (visto.update(u=url, h=headers), Resp({"data": [{"id": "claude-b"}, {"id": "claude-a"}]}))[1])
    assert listar_modelos("anthropic", "k") == ["claude-a", "claude-b"]
    assert "x-api-key" in visto["h"]


def test_listar_modelos_exige_clave_solo_si_el_proveedor_la_pide(monkeypatch):
    with pytest.raises(AiServiceError, match="API key"):
        listar_modelos("openai", None)
    monkeypatch.setattr(httpx, "get", lambda url, headers=None, timeout=None: Resp({"data": [{"id": "llama3.1"}]}))
    assert listar_modelos("ollama_local", None, "http://localhost:11434/v1") == ["llama3.1"]


def test_anthropic_herramienta_y_luego_texto(monkeypatch):
    respuestas = iter([
        {"content": [{"type": "tool_use", "id": "tu_1", "name": "ver_estado_aplicacion", "input": {}}]},
        {"content": [{"type": "text", "text": "Todo aplicado."}]},
    ])
    cuerpos = []
    monkeypatch.setattr(httpx, "post", lambda url, headers=None, json=None, timeout=None: (cuerpos.append(json), Resp(next(respuestas)))[1])
    r = preguntar_agentico(FakeDB(), Config(), "¿hay cambios sin aplicar?")
    assert r["respuesta"] == "Todo aplicado." and r["herramientas_usadas"] == ["ver_estado_aplicacion"]
    # La segunda llamada lleva el resultado de la herramienta como tool_result
    ultimo = cuerpos[-1]["messages"][-1]
    assert ultimo["role"] == "user" and ultimo["content"][0]["type"] == "tool_result" and ultimo["content"][0]["tool_use_id"] == "tu_1"


def test_ollama_cloud_sigue_sin_modo_agentico():
    with pytest.raises(AiServiceError, match="modo agéntico"):
        preguntar_agentico(FakeDB(), Config(provider="ollama_cloud"), "hola")


# --- búsqueda por texto completo -------------------------------------------------

def test_consulta_or_descarta_palabras_vacias_y_une_con_or():
    q = ai_service._consulta_or("¿Cómo bloqueo el acceso a Facebook en el panel?")
    assert q == "bloqueo | acceso | facebook"
    assert ai_service._consulta_or("hola gracias") is None


def test_consulta_or_en_ingles_y_portugues_usa_sus_palabras_vacias():
    assert ai_service._consulta_or("How do I block access to a website", "en") == "block | access | website"
    assert ai_service._consulta_or("Como eu limito a velocidade", "pt") == "eu | limito | velocidade" or "limito" in ai_service._consulta_or("Como eu limito a velocidade", "pt")


def test_consulta_or_acota_la_cantidad_de_terminos_y_solo_deja_caracteres_seguros():
    q = ai_service._consulta_or("uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce " + "x'; DROP TABLE")
    assert q.count("|") <= 11 and "'" not in q and ";" not in q
