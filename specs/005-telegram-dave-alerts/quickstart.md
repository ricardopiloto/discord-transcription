# Quickstart: Telegram DAVE alerts

**Feature**: `005-telegram-dave-alerts`  
**Goal**: Validar envio direto ao Telegram nos três eventos DAVE, sem webhook mid-session.

## Prerequisites

1. Cronista com feature 004 (DAVE recovery) operacional
2. Bot Telegram criado via [@BotFather](https://t.me/BotFather) → Token
3. Chat/grupo de destino; obter Chat ID (ex.: mensagem ao bot + `getUpdates`, ou bot auxiliar)
4. Bot adicionado ao grupo (se destino for grupo) com permissão de enviar mensagens
5. Rede do host Cronista alcança `https://api.telegram.org` (ou `CRONISTA_TELEGRAM_API_BASE`)

## Setup

No `.env` do Cronista (não commitar secrets):

```bash
CRONISTA_TELEGRAM_BOT_TOKEN=<token>
CRONISTA_TELEGRAM_CHAT_ID=<chat_id>
# opcional:
# CRONISTA_TELEGRAM_API_BASE=https://api.telegram.org
```

Remover / deixar vazio qualquer `CRONISTA_ALERT_WEBHOOK_URL` legado.

Reiniciar o serviço Cronista.

## Unit tests (sem Telegram real)

```bash
cd app
.venv/bin/pytest tests/unit/test_telegram_alert.py -q
```

Esperado: formatação `Xm Ys` / ISO UTC; omitir sem credenciais; retries; token não aparece em logs capturados.

## Manual — ciclo recovered

1. Iniciar gravação em canal de teste (`!cronista iniciar` / fluxo atual).
2. Forçar cenário de recovery DAVE (mesmo procedimento do [quickstart 004](../004-dave-decrypt-recovery/quickstart.md) — ex. disconnect completo / falhas de decriptação).
3. **Antes do fim da sessão**, no chat Telegram:
   - Mensagem de detecção com nome do canal
   - Mensagem de recuperação com duração no formato `2m 15s` ou `45s` (não só `42s` decimal antigo se ≥ 60s)
4. Confirmar que a reconexão **começou** mesmo se a API Telegram estiver lenta (detecção não bloqueia).
5. Encerrar sessão; n8n session-end (se configurado) continua funcionando; `gap_count` se aplicável.

## Manual — ciclo failed (opcional)

1. Impedir reconnect bem-sucedido (ex. sem permissão de voz / canal inválido após disconnect) até esgotar tentativas.
2. Esperar mensagem crítica com `{N}` e `{horário}` ISO-8601 UTC.
3. Sessão permanece aberta; bot fora do voz (comportamento 004).

## Manual — credenciais ausentes

1. Remover Token ou Chat ID; reiniciar.
2. Disparar recovery.
3. Logs: omissão de alerta Telegram; gaps + recovery seguem; **nenhuma** chamada à Bot API.

## Manual — API inacessível

1. Apontar `CRONISTA_TELEGRAM_API_BASE` para host inválido (ou firewall).
2. Disparar recovery.
3. Até 3 tentativas no log; recovery conclui; Token não aparece no log.

## Pass / Fail

| Check | Pass |
|-------|------|
| Textos batem Message Templates da spec | ☐ |
| Duração legível + horário ISO UTC no failed | ☐ |
| Sem `CRONISTA_ALERT_WEBHOOK_URL` necessário | ☐ |
| Detect paralelo (reconnect não espera Telegram) | ☐ |
| n8n fim de sessão intacto | ☐ |
| Token ausente dos logs | ☐ |

## References

- [contracts/api.md](./contracts/api.md)
- [data-model.md](./data-model.md)
- [spec.md](./spec.md)
