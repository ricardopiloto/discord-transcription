# Demanda — whisper-service

## Objetivo

Microserviço HTTP local que expõe o `faster-whisper` para o workflow "Cronista - Transcrição da Sessão" no n8n. Carrega o modelo uma única vez na inicialização e atende múltiplas chamadas de transcrição sem recarregar.

## Contrato de API

### `POST /transcribe`

Request:
```json
{
  "audio_path": "/opt/apps/cronista/recordings/20260710-2201/123456789/0001.ogg",
  "language": "pt"
}
```

Response (200):
```json
{
  "text": "Vocês entram na taverna e sentem o cheiro de cerveja derramada.",
  "language": "pt",
  "duration_s": 4.2
}
```

Response (404) — arquivo não encontrado:
```json
{ "detail": "Arquivo não encontrado: /caminho/informado.ogg" }
```

Response (500) — falha na transcrição:
```json
{ "detail": "mensagem do erro original" }
```

### `GET /health`

```json
{ "status": "ok", "model": "small", "compute_type": "int8" }
```

## Configuração (variáveis de ambiente)

| Variável | Default | Descrição |
|---|---|---|
| `WHISPER_MODEL_SIZE` | `small` | `tiny`/`base`/`small`/`medium`/`large-v3` |
| `WHISPER_COMPUTE_TYPE` | `int8` | quantização, otimizado pra CPU |
| `WHISPER_CPU_THREADS` | `5` | limite de threads do CTranslate2 — deixa núcleos livres pro resto da stack do servidor (Foundry, Bertroldo, n8n, blog). Sem esse limite, o motor tenta usar todos os núcleos disponíveis por chamada |
| `WHISPER_HOST` | `0.0.0.0` | precisa ser `0.0.0.0`, não `127.0.0.1` — o n8n roda em container Docker e alcança o host via `host.docker.internal`, que não é tratado como tráfego de loopback |
| `WHISPER_PORT` | `8008` | porta do serviço |

## Requisitos não-funcionais

- **Bind obrigatório em `0.0.0.0`**: um bind em `127.0.0.1` rejeita conexões vindas da rede bridge do Docker.
- **Processo único (`--workers 1`)**: o modelo é carregado em memória uma vez por worker; múltiplos workers duplicariam o uso de RAM sem ganho real, já que as chamadas hoje chegam sequenciais do n8n.
- **`cpu_threads` configurável e limitado por padrão**: motivo de performance do servidor compartilhado — evitar que uma transcrição em lote sature todos os núcleos e afete Foundry/Bertroldo/blog rodando ao mesmo tempo.
- **Sem autenticação**: a segurança do serviço depende de isolamento de rede (firewall), não de token — está documentado como restrição conhecida, não como pendência de implementação.

## Fora de escopo

- Upload de arquivo binário via HTTP — recebe apenas um caminho de arquivo já presente em disco.
- Fila de processamento / concorrência real.
- Suporte a GPU nesta fase.
- Diarização, tradução.

## Critérios de aceite

- `/health` responde depois do processo subir, confirmando modelo carregado.
- `/transcribe` com um `.ogg` real retorna texto coerente em português.
- `/transcribe` com caminho inexistente retorna 404 com mensagem clara.
- Serviço acessível a partir de um container Docker na mesma máquina via `host.docker.internal`.
- Uma transcrição de sessão completa (~2.000 utterances) não deixa a CPU saturada a ponto de outros serviços do servidor ficarem perceptivelmente lentos (validar com `htop` durante um teste real).
