from __future__ import annotations

import asyncio
import os
from dataclasses import replace
from typing import Dict

from flask import Flask, render_template, request, redirect, url_for, flash

from config import Config, ModelConfig
from agents.orchestrator import DebateOrchestrator
from models.api_client import ModelManager


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

    neuroapi_models = [
        ("gpt-5-thinking-all", "gpt-5-thinking-all"),
    ]

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

        # Run debate synchronously via asyncio
        session_id = f"web_{os.getpid()}"

        async def run():
            async with ModelManager(models_config, session_id=session_id) as mm:
                orchestrator = DebateOrchestrator(mm)
                return await orchestrator.run_debate(query, session_id=session_id)

        try:
            session = asyncio.run(run())
        except Exception as e:
            flash(f"Ошибка запуска дебатов: {e}", "error")
            return redirect(url_for("index", provider=provider))

        # Prepare data for rendering
        # rounds_data: list of dict with arguments and judge info
        rounds_data = []
        if session.context and session.context.arguments_history:
            for round_num in sorted(session.context.arguments_history.keys()):
                args_map = session.context.arguments_history.get(round_num, {})
                scores = session.context.scores_history.get(round_num, {}) if session.context.scores_history else {}
                judge_fb = session.context.judge_feedback.get(round_num, "") if session.context.judge_feedback else ""
                rounds_data.append({
                    "round": round_num,
                    "arguments": args_map,
                    "scores": scores,
                    "judge_feedback": judge_fb,
                })

        return render_template(
            "result.html",
            provider=provider,
            query=session.original_query,
            enhanced_query=session.enhanced_query,
            status=session.status,
            rounds=rounds_data,
            final_verdict=session.final_verdict,
            token_stats=session.token_stats,
        )

    return app


if __name__ == "__main__":
    # Allow FLASK_RUN_PORT or default 5000
    port = int(os.getenv("PORT", os.getenv("FLASK_RUN_PORT", 5000)))
    host = os.getenv("FLASK_RUN_HOST", "0.0.0.0")
    app = create_app()
    app.run(host=host, port=port, debug=os.getenv("FLASK_DEBUG", "0") == "1")

