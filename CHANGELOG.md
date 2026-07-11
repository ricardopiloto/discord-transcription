# Changelog

Todas as mudanças notáveis deste projeto serão documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o versionamento segue [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [Unreleased]

### Planejado

- Executar spike DAVE no ambiente real e registrar verdict em `specs/002-python-pycord-migration/contracts/spike-acceptance.md`
- Validar quickstart manual completo (Discord ao vivo)
- Confirmar captura de áudio e estabilidade em sessão prolongada

---

## [0.1.1] - 2026-07-11

> **Status**: correções de deploy e voz em teste de produção — `!cronista entrar` funcional após fix da API py-cord 2.8.

### Fixed

- **`!cronista entrar` quebrava com `TypeError`** — py-cord 2.8 não aceita `self_deaf`/`self_mute` em `channel.connect()`; conexão agora usa `connect()` + `guild.change_voice_state(...)` (`app/cronista/commands.py`, `spike/record_smoke.py`)
- **Callback de gravação incompatível** — `start_recording` em py-cord 2.8 chama o callback só com `exception`, não `(sink, channel, exception)` (`app/cronista/session_manager.py`)
- **Sink não processava áudio** — `Sink.write` recebe `VoiceData` com PCM em `.pcm`; sink ajustado para extrair bytes corretamente (`app/cronista/recording/sink.py`)

### Changed

- Documentação de deploy reescrita para **clone git direto** em `/opt/apps/cronista` (substitui fluxo com `rsync`)
- README: seção passo a passo **"Configuração do bot Discord"** (Developer Portal, intents, convite, `.env`, verificação)
- Link de convite manual atualizado com permissão **Speak** (`permissions=3214336`)
- Contratos e tasks alinhados à API real do py-cord 2.8

### Removed

- Stack Node/TypeScript legada (`src/`, `tests/`, `package.json`, `tsconfig.json`, `eslint.config.js`)

---

## [0.1.0] - 2026-07-10

> **Status**: implementação inicial Python — **não validada** em sessão real.

Primeira versão do Cronista em Python/py-cord, substituindo o protótipo Node/TypeScript.

### Added

- Bot Discord em Python 3.11+ (`app/cronista/`)
  - Comandos `!cronista entrar`, `!cronista encerrar`, `!cronista status`, `!cronista help`
  - `SessionManager` — ciclo de vida da sessão, participantes, guard de sessão única
  - `IncrementalUtteranceSink` — gravação incremental por utterance (sem buffer de sessão inteira em RAM)
  - Delimitação de utterances por silêncio configurável (`UTTERANCE_SILENCE_MS`, default 1s)
  - Conversão PCM→Opus via ffmpeg ao fechar cada segmento (fallback `.wav` se ffmpeg ausente)
  - Encerramento automático quando canal de voz fica vazio (`AUTO_END_EMPTY_CHANNEL_MS`, default 5 min)
  - Webhook n8n com retry exponencial (3 tentativas, 1s/2s/4s) e flag `webhook_failed`
- Spike de validação DAVE (`spike/record_smoke.py`) com CLI e SpikeResult JSON
- Artefatos de sessão compatíveis com spec 001:
  - `recordings/{session_id}/session.json`
  - `recordings/{session_id}/speaking_log.jsonl`
  - `recordings/{session_id}/{user_id}/NNNN.ogg`
- Testes unitários (`app/tests/unit/`) — storage helpers e webhook retry (5 testes)
- Deploy systemd para Python (`deploy/cronista.service`)
- Specs e design da migração (`specs/002-python-pycord-migration/`)
- Constituição do projeto v1.0.0 (`.specify/memory/constitution.md`)
- PRD v2 em `docs/PRD-bot-cronista-transcricao_v2.md`
- `.env.example` com variáveis de configuração

### Changed

- Stack de runtime: Node.js/TypeScript → Python 3.11+ / py-cord
- `README.md` reescrito para setup, deploy e arquitetura Python
- `.gitignore` atualizado para artefatos Python (venv, `__pycache__`, pytest cache)

### Documentation

- Spec 001 (`specs/001-voice-capture-bot/`) — MVP original Node, mantida como referência de contratos
- Checklist de validação (`specs/002-python-pycord-migration/checklists/implementation-validation.md`)

---

## Histórico anterior (pré-0.1.0, removido do tree)

Protótipo Node/TypeScript implementado e depois substituído nesta release. Funcionalidades portadas:

- Gravação Opus→Ogg por utterance (`@discordjs/voice` + `prism-media`)
- Comandos `!cronista`, webhook n8n, auto-end por canal vazio
- Abandonado por risco de recepção de áudio sob protocolo DAVE do Discord
