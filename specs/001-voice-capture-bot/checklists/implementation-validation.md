# Implementation Validation Checklist

**Feature**: 001-voice-capture-bot  
**Created**: 2026-07-10  
**Guide**: [quickstart.md](./quickstart.md)

Validação manual no Discord — requer `DISCORD_TOKEN` configurado.

| # | Scenario | Pass |
|---|----------|------|
| 1 | Iniciar captura (`!cronista entrar`) | ☐ |
| 2 | Captura por jogador (2+ falantes) | ☐ |
| 3 | Status durante sessão | ☐ |
| 4 | Encerrar + webhook | ☐ |
| 5 | Auto-end canal vazio | ☐ |
| 6 | Coexistência Robigode | ☐ |
| 7 | Sessão duplicada rejeitada | ☐ |
| 8 | Webhook failure marcado | ☐ |
| 9 | Estabilidade 30min+ | ☐ |

**Automated checks passed**:
- `npm run typecheck`
- `npm run build`
- `npm test` (unit tests)
