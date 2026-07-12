# Changelog

Todas as mudanças notáveis deste projeto serão documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o versionamento segue [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [Unreleased]

### Planejado

- Executar spike DAVE no ambiente real e registrar verdict em `specs/002-python-pycord-migration/contracts/spike-acceptance.md`
- Validar quickstart manual completo (Discord ao vivo)
- Confirmar captura de áudio e estabilidade em sessão prolongada

---

## [0.1.6] - 2026-07-12

> **Status**: gravação sem deadlock no event loop — aguardando revalidação em produção.

### Fixed

- **Gravação travava com `TimeoutError` e heartbeat bloqueado** — `write()` bloqueava o event loop do Discord com `future.result()` enquanto aguardava `_start_utterance()` assíncrono; abertura de arquivo WAV agora é síncrona e registro de participante é agendado sem bloquear (`app/cronista/recording/sink.py`)
- **Nome de participante não atualizava após resolução via API** — `register_participant` agora substitui placeholder `user-{id}` quando o nome real é obtido (`app/cronista/session_manager.py`)

---

## [0.1.5] - 2026-07-12

> **Status**: decodificação Opus→PCM no sink — aguardando revalidação de arquivos `.ogg` em produção.

### Fixed

- **Áudio não gravava apesar de pacotes recebidos** — `IncrementalUtteranceSink` agora implementa `is_opus() → False`, instruindo o py-cord a decodificar Opus para PCM antes de `write()`; sem isso o sink recebia dados vazios e não criava arquivos (`app/cronista/recording/sink.py`)

### Changed

- `README.md`: pipeline de áudio documentado (Opus→PCM→WAV→OGG) e sinal de log esperado ao capturar

### Added

- Teste unitário garantindo `is_opus() == False` no sink (`app/tests/unit/test_sink.py`)

---

## [0.1.4] - 2026-07-12

> **Status**: documentação de deploy para Ubuntu 26.04 / Python 3.14 — requer venv com 3.13.

### Changed

- Runtime documentado e fixado em `>=3.11,<3.14` (`app/pyproject.toml`) — py-cord não suporta Python 3.14
- `README.md`: requisitos de Python 3.11–3.13 explícitos; guia **Ubuntu 26.04** com Python 3.13 via deadsnakes; seção para recriar venv quando `pip` falha com `not in '<3.14,>=3.10'`
- `app/requirements.txt`: comentário sobre incompatibilidade com Python 3.14

---

## [0.1.3] - 2026-07-11

> **Status**: participantes + recepção DAVE corrigidos — aguardando revalidação com áudio ao vivo.

### Fixed

- **Participantes não apareciam em `session.json` / `!cronista status`** — bot não usa `members` intent; participantes do canal são pré-registrados ao iniciar, novos entrantes são registrados via `on_voice_state_update`, e resolução de nome usa `voice_channel.members` → `fetch_member` → `fetch_user` → fallback (`app/cronista/recording/sink.py`, `app/cronista/session_manager.py`, `app/cronista/bot.py`)
- **Gravação ignorada sem `Member` no cache** — user_id obtido via mapeamento SSRC quando py-cord envia `source=None`
- **Nenhum arquivo de áudio gerado sob DAVE** — py-cord 2.8.0 (PyPI) não decodifica frames criptografados; `requirements.txt` passa a usar PR #3202 com fix de recepção DAVE
- Logs de diagnóstico no sink quando pacotes PCM chegam (ou quando user_id não está mapeado)

### Changed

- Dependência de voz: `py-cord[voice]` instalado a partir do PR #3202 até merge oficial na release estável

### Added

- Testes unitários para resolução de participante e extração de user_id via SSRC (`app/tests/unit/test_sink.py`)

---

## [0.1.2] - 2026-07-11

> **Status**: `!cronista entrar` funcional em produção após fix do `start_recording`.

### Fixed

- **`!cronista entrar` falhava após conectar ao canal** — py-cord 2.8 exige `__sink_listeners__` e `walk_children()` em sinks customizados; ausência desses atributos gerava `AttributeError` silencioso e desconectava o bot (`app/cronista/recording/sink.py`, `spike/record_smoke.py`)
- **Sessão órfã em memória** — falha parcial em `SessionManager.start()` deixava `is_recording=True` sem gravação ativa; rollback via `_reset()` adicionado
- **`reply` de confirmação derrubava a gravação** — erro ao enviar mensagem de sucesso não desconecta mais o canal de voz (`app/cronista/commands.py`)
- **Sink sem referência ao voice client** — `sink.init(voice_client)` chamado antes de `start_recording` (`app/cronista/session_manager.py`)

### Added

- Teste unitário de compatibilidade do sink com o router de voz do py-cord 2.8 (`app/tests/unit/test_sink.py`)

---

## [0.1.1] - 2026-07-11

> **Status**: conectava ao canal de voz, mas `start_recording` ainda quebrava em produção (corrigido em 0.1.2).

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
