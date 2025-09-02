from __future__ import annotations

import asyncio
import json
import os
from dataclasses import replace
from typing import Dict, List, Tuple

from flask import Flask, render_template, request, redirect, url_for, flash, Response
from flask import stream_with_context
import threading
import queue
import markdown as md
import bleach

from config import Config, ModelConfig
from agents.orchestrator import DebateOrchestrator
from models.api_client import ModelManager


def load_neuroapi_models() -> List[Tuple[str, str]]:
    """Загружает список моделей из JSON файла"""
    try:
        with open('neuroapi_models.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            models = []
            for model_id, model_info in data['models'].items():
                display_name = model_info.get('display_name', model_id)
                models.append((model_id, display_name))
            return models
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        # Возвращаем дефолтную модель если файл не найден или поврежден
        return [("gpt-5-thinking-all", "gpt-5-thinking-all")]


def build_models_config(provider: str, per_role_models: Dict[str, str]) -> Dict[str, ModelConfig]:
    """Builds a models config dict based on provider and selected model IDs per role.

    - provider: "neuroapi" or "openrouter"
    - per_role_models: mapping role -> model_id
    """
    base = Config.NEUROAPI_MODELS if provider == "neuroapi" else Config.MODELS

    final: Dict[str, ModelConfig] = {}
    for role, base_cfg in base.items():
        chosen = per_role_models.get(role, base_cfg.model_id)
        final[role] = replace(base_cfg, model_id=chosen)
    return final


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret")

    # Available models for selection per provider
    openrouter_models = [
        ("google/gemini-2.5-flash-lite-preview-06-17", "Gemini 2.5 Flash Lite"),
        ("google/gemini-2.5-flash", "Gemini 2.5 Flash"),
        ("openai/gpt-4o-mini-2024-07-18", "GPT-4o Mini"),
        ("google/gemini-2.5-pro", "Gemini 2.5 Pro"),
        ("anthropic/claude-sonnet-4", "Claude Sonnet 4"),
        ("openai/gpt-4.1", "GPT-4.1"),
        ("openai/o3", "OpenAI o3"),
    ]

    neuroapi_models = load_neuroapi_models()

    roles = [
        ("gatekeeper", "Gatekeeper"),
        ("debater_pro", "Debater PRO (D1)"),
        ("debater_contra", "Debater CONTRA (D2)"),
        ("debater_alternative", "Debater ALT (D3)"),
        ("judge", "Judge"),
    ]

    def ensure_api_keys(provider: str) -> bool:
        if provider == "neuroapi":
            return bool(Config.NEUROAPI_API_KEY and Config.NEUROAPI_API_KEY != "your-neuroapi-key")
        else:
            return bool(Config.OPENROUTER_API_KEY and Config.OPENROUTER_API_KEY != "your-openrouter-key")

    @app.get("/")
    def index():
        provider = request.args.get("provider") or Config.PROVIDER
        model_options = neuroapi_models if provider == "neuroapi" else openrouter_models

        # Defaults from current config for each role
        base = Config.get_models() if provider == Config.PROVIDER else (
            Config.NEUROAPI_MODELS if provider == "neuroapi" else Config.MODELS
        )
        defaults = {role: base[role].model_id for role, _ in roles}

        return render_template(
            "index.html",
            provider=provider,
            roles=roles,
            model_options=model_options,
            defaults=defaults,
        )

    @app.post("/debate")
    def debate():
        provider = request.form.get("provider", Config.PROVIDER)
        query = request.form.get("query", "").strip()
        # If this is a confirmed run (coming from choose page), redirect to streaming
        final_query = request.form.get("final_query")
        original_query = request.form.get("original_query")
        enhanced_query_param = request.form.get("enhanced_query")

        if not query:
            flash("Введите вопрос для дебатов", "error")
            return redirect(url_for("index", provider=provider))

        if not ensure_api_keys(provider):
            need = "NEUROAPI_API_KEY" if provider == "neuroapi" else "OPENROUTER_API_KEY"
            flash(f"Отсутствует API ключ {need}. Установите его в .env и перезапустите.", "error")
            return redirect(url_for("index", provider=provider))

        # Collect selected models per role
        per_role_models = {}
        for role, _ in roles:
            per_role_models[role] = request.form.get(role) or (
                Config.NEUROAPI_MODELS if provider == "neuroapi" else Config.MODELS
            )[role].model_id

        models_config = build_models_config(provider, per_role_models)

        # First stage: show original vs enhanced and let user choose
        # Run only gatekeeper + enhancement here, then stream the debate on confirmation
        session_id = f"web_{os.getpid()}"

        async def prepare():
            async with ModelManager(models_config, session_id=session_id) as mm:
                orchestrator = DebateOrchestrator(mm)
                # Only gatekeeper and enhancement
                should_debate, rejection_reason = await orchestrator.gatekeeper.should_debate(query)
                if not should_debate:
                    return {"rejected": True, "reason": rejection_reason}
                enhanced = await orchestrator.gatekeeper.get_enhanced_query(query)
                return {"rejected": False, "enhanced": enhanced}

        try:
            prep = asyncio.run(prepare())
        except Exception as e:
            flash(f"Ошибка подготовки дебатов: {e}", "error")
            return redirect(url_for("index", provider=provider))

        if prep.get("rejected"):
            flash(f"Запрос отклонен: {prep.get('reason')}", "error")
            return redirect(url_for("index", provider=provider))

        enhanced_query = prep.get("enhanced", query)

        # Render choice page
        return render_template(
            "choose.html",
            provider=provider,
            roles=roles,
            model_options=(neuroapi_models if provider == "neuroapi" else openrouter_models),
            # preserve selected models
            defaults={role: per_role_models.get(role, "") for role, _ in roles},
            original_query=query,
            enhanced_query=enhanced_query,
        )

    def _markdown_to_html(text: str) -> str:
        if not text:
            return ""
        # Basic Markdown -> HTML with sanitization
        html = md.markdown(
            text,
            extensions=["fenced_code", "tables", "sane_lists", "nl2br"]
        )
        allowed_tags = set(bleach.sanitizer.ALLOWED_TAGS).union({
            'p', 'pre', 'code', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'table', 'thead', 'tbody', 'tr', 'th', 'td', 'hr', 'blockquote'
        })
        allowed_attrs = {
            **bleach.sanitizer.ALLOWED_ATTRIBUTES,
            'a': ['href', 'title', 'rel', 'target']
        }
        clean = bleach.clean(html, tags=list(allowed_tags), attributes=allowed_attrs)
        return clean

    def _js_escape(text: str) -> str:
        if text is None:
            return ""
        # Escape for embedding inside JS template literal
        return (
            text
            .replace('\\', r'\\')
            .replace('`', r'\`')
            .replace('${', r'\${')
        )

    @app.post("/debate_stream")
    def debate_stream():
        provider = request.form.get("provider", Config.PROVIDER)
        original_query = request.form.get("original_query", "").strip()
        enhanced_query = request.form.get("enhanced_query", original_query).strip()
        use = request.form.get("use", "enhanced")  # 'original' or 'enhanced'

        if not original_query:
            flash("Введите вопрос для дебатов", "error")
            return redirect(url_for("index", provider=provider))

        # Collect selected models per role
        per_role_models = {}
        for role, _ in roles:
            per_role_models[role] = request.form.get(role) or (
                Config.NEUROAPI_MODELS if provider == "neuroapi" else Config.MODELS
            )[role].model_id

        models_config = build_models_config(provider, per_role_models)

        session_id = f"web_{os.getpid()}"
        q: "queue.Queue[str]" = queue.Queue()

        def write_chunk(html: str):
            try:
                q.put(html)
            except Exception:
                pass

        def on_update(event: str, payload: Dict):
            # Transform payloads to immediate HTML appends
            if event == "enhanced_query":
                eq = payload.get("enhanced_query", "")
                write_chunk(f"<script>window.updateEnhanced(`{_js_escape(eq)}`);</script>\n")
            elif event == "argument":
                rnd = payload.get("round")
                role = payload.get("role")
                text = _markdown_to_html(payload.get("text", ""))
                write_chunk(f"<script>window.appendArgument({int(rnd)}, '{role}', `{_js_escape(text)}`);</script>\n")
            elif event == "summary":
                rnd = payload.get("round")
                role = payload.get("role")
                s = bleach.clean(payload.get("summary", ""))
                write_chunk(f"<script>window.appendSummary({int(rnd)}, '{role}', `{_js_escape(s)}`);</script>\n")
            elif event == "judge":
                rnd = payload.get("round")
                fb = _markdown_to_html(payload.get("feedback", ""))
                write_chunk(f"<script>window.appendJudge({int(rnd)}, `{_js_escape(fb)}`);</script>\n")
            elif event == "final_verdict":
                fv = _markdown_to_html(payload.get("final_verdict", ""))
                write_chunk(f"<script>window.showFinalVerdict(`{_js_escape(fv)}`);</script>\n")
            elif event == "token_stats":
                ts = bleach.clean(payload.get("token_stats", ""))
                write_chunk(f"<script>window.showTokenStats(`{_js_escape(ts)}`);</script>\n")

        def run_async():
            async def run():
                async with ModelManager(models_config, session_id=session_id) as mm:
                    orchestrator = DebateOrchestrator(mm)
                    # Determine chosen query
                    chosen = original_query if use == "original" else enhanced_query
                    try:
                        await orchestrator.run_debate(
                            query=original_query,
                            session_id=session_id,
                            override_query=chosen,
                            known_enhanced=enhanced_query,
                            skip_enhance=True,
                            skip_gatekeeper=True,
                            on_update=on_update,
                        )
                    except Exception as e:
                        write_chunk(f"<div class='flash error'>Ошибка: {str(e)}</div>")
            asyncio.run(run())
            write_chunk("<script>window.markDone();</script>")
            # Сентинел для завершения генератора
            try:
                q.put(None)
            except Exception:
                pass

        threading.Thread(target=run_async, daemon=True).start()

        @stream_with_context
        def generate():
            # Initial HTML shell + padding to defeat buffering
            initial = render_template(
                "stream.html",
                provider=provider,
                original_query=original_query,
                enhanced_query=enhanced_query,
                use=use,
            )
            yield initial
            yield "\n" + (" " * 4096) + "\n"
            yield "<script>console.log('stream-start');</script>\n"
            while True:
                chunk = q.get()
                if not chunk:
                    break
                yield chunk

        resp = Response(generate(), mimetype='text/html')
        # Disable proxy buffering if any
        resp.headers['X-Accel-Buffering'] = 'no'
        resp.headers['Cache-Control'] = 'no-cache'
        return resp

    return app


if __name__ == "__main__":
    # Allow FLASK_RUN_PORT or default 5000
    port = int(os.getenv("PORT", os.getenv("FLASK_RUN_PORT", 5001)))
    host = os.getenv("FLASK_RUN_HOST", "0.0.0.0")
    app = create_app()
    app.run(host=host, port=port, debug=os.getenv("FLASK_DEBUG", "0") == "1")
