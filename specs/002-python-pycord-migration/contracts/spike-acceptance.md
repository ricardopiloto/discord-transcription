# Contract: Spike de Recepção sob DAVE (gate de migração)

**Feature**: 002-python-pycord-migration  
**Cobre**: US1, FR-001, FR-002, SC-001

Este contrato define o critério **objetivo** que libera (ou bloqueia) o rewrite completo em Python. É executado **antes** da Phase B do plano.

## Objetivo

Provar empiricamente que a stack py-cord escolhida recebe e grava áudio real em um canal de voz Discord com DAVE ativo, no ambiente do servidor alvo.

## Procedimento

1. Provisionar venv Python isolado com uma `pycord_source` candidata (release estável, branch com PR #3202, ou fork + `davey`).
2. Rodar `spike/record_smoke.py`: bot entra no canal de teste e grava por ≥ 3 minutos.
3. Pelo menos **2 participantes humanos** falam alternadamente durante a captura.
4. Encerrar e inspecionar os arquivos gerados.

## Resultado (SpikeResult)

Registrar o resultado preenchendo:

```json
{
  "pycord_source": "PENDING — run spike/record_smoke.py",
  "dave_active": null,
  "packets_received": 0,
  "duration_s": 0,
  "audio_playable": false,
  "authorship_correct": false,
  "verdict": "PENDING"
}
```

**Status**: Script implementado (`spike/record_smoke.py`). Execução manual pendente — requer `DISCORD_TOKEN` e canal de voz real.

```bash
cd /home/ricardosobral/Documents/Desenvolvimento/discord-transcription
python3.11 -m venv .venv-spike && . .venv-spike/bin/activate
pip install "py-cord[voice]"
export DISCORD_TOKEN=...
python spike/record_smoke.py --channel <voice_channel_id> --seconds 180
```

## Critérios de Aceitação (PASS)

Todos devem ser verdadeiros para `verdict = PASS`:

- [ ] `dave_active = true` no canal de teste (não é um canal legado sem DAVE)
- [ ] `packets_received > 0` de forma contínua (não apenas os ~5% de frames passthrough)
- [ ] Foram gerados ≥ 3 minutos de áudio
- [ ] `audio_playable = true` — arquivos reproduzem voz audível
- [ ] `authorship_correct = true` — áudio de cada usuário está no diretório do usuário correto
- [ ] Sem crash do processo durante a captura

## Gate

| Verdict | Ação |
|---------|------|
| **PASS** | Libera Phase B+ com a `pycord_source` confirmada fixada em `requirements.txt` |
| **FAIL** | Bloqueia rewrite. Registrar diagnóstico. Opções: (a) testar outra `pycord_source`; (b) acionar fallback de reavaliar Node (spec §Propostas) com spike equivalente; (c) aguardar merge do fix DAVE |
| **PENDING** | Código do spike pronto; aguardando execução manual no ambiente real |

## Notas

- A documentação estável da py-cord (v2.8.x) ainda emite `RuntimeWarning` de recepção quebrada sob DAVE (issue #3139); a correção está no PR #3202. Por isso este spike não é formalidade — é a validação do maior risco do projeto.
- O spike é **descartável**: não faz parte do pacote de produção e pode ser removido após a decisão.
- **Implementação Python completa foi adiantada** com py-cord estável como candidato default; cutover de produção MUST aguardar verdict PASS.
