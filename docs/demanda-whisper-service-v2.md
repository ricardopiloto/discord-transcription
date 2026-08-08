# Demanda — whisper-service (v2: processamento por sessão, assíncrono)

## Contexto da mudança

A v1 (endpoint `/transcribe` por utterance, chamado pelo n8n em loop) mostrou-se frágil em produção: ~664-2.000 chamadas HTTP sequenciais atravessando a rede Docker geraram timeouts, execuções duplicadas e falhas silenciosas difíceis de diagnosticar. Esta versão move o processamento em lote pra dentro do próprio serviço, reduzindo a interação com o n8n a duas chamadas por sessão.

Os endpoints `POST /transcribe` (utterance única) e `GET /health` da v1 continuam válidos — úteis pra debug pontual — mas deixam de ser o caminho principal do pipeline.

## Novos endpoints

### `POST /transcribe-session`

Recebe os dados de uma sessão inteira, responde **imediatamente** (202) e processa em background.

Request:
```json
{
  "session_id": "20260807-231300",
  "recordings_path": "/opt/apps/cronista/recordings/20260807-231300",
  "speaking_log_path": "/opt/apps/cronista/recordings/20260807-231300/speaking_log.jsonl",
  "participants": [
    { "user_id": "693962506573578270", "display_name": "Ricardo", "utterance_count": 42 }
  ],
  "channel_id": "id_do_canal_discord",
  "callback_url": "http://127.0.0.1:5678/webhook/cronista-transcricao-concluida"
}
```

Response (202) — aceito, processamento iniciado em background:
```json
{ "status": "accepted", "session_id": "20260807-231300" }
```

Response (409) — já existe processamento em andamento pra essa sessão (ver seção de lock):
```json
{ "detail": "Sessão 20260807-231300 já está sendo processada" }
```

**Comportamento em background:**
1. Lê `speaking_log_path` direto do disco (o serviço já roda no host, sem restrição de path como o n8n em Docker).
2. Para cada utterance, chama `model.transcribe()` **em processo**, sem HTTP — é uma chamada de função Python normal.
3. Ordena por `start_ms`, formata `[HH:MM:SS] Nome: texto` usando `participants` pra mapear `user_id` → `display_name` (mesma lógica que já existia no node "Montar transcrição final" do n8n — ela migra pra cá).
4. Escreve `transcricao.txt` em `recordings_path`.
5. Dispara `POST` pro `callback_url` avisando que terminou (ver seção de callback).
6. Atualiza o status interno da sessão (ver `/status`) em cada etapa, não só no fim — assim o `/status` reflete progresso real durante o processamento, não só o resultado final.

### `GET /status/{session_id}`

Consulta de progresso, sem precisar grepar log.

Em andamento:
```json
{ "status": "in_progress", "processed": 340, "total": 664, "started_at": "2026-08-08T02:52:00Z" }
```

Concluído:
```json
{
  "status": "done",
  "processed": 664,
  "total": 664,
  "utterances_com_texto": 610,
  "output_path": "/opt/apps/cronista/recordings/20260807-231300/transcricao.txt",
  "finished_at": "2026-08-08T04:15:00Z"
}
```

Falhou:
```json
{ "status": "failed", "error": "mensagem do erro", "processed": 210, "total": 664 }
```

Sessão desconhecida (404): nunca foi iniciada, ou o processo reiniciou desde então (status é em memória, não persiste — ver Restrições).

### Callback ao terminar (chamado pelo whisper-service, não pelo n8n)

`POST` para o `callback_url` recebido na request original:

```json
{
  "session_id": "20260807-231300",
  "status": "done",
  "output_path": "/opt/apps/cronista/recordings/20260807-231300/transcricao.txt",
  "total_utterances": 664,
  "utterances_com_texto": 610,
  "channel_id": "id_do_canal_discord"
}
```

Em caso de falha total, `status: "failed"` com um campo `error` no lugar de `output_path`.

## Requisitos de implementação

### Concorrência e trava por sessão

Antes de iniciar o processamento de uma `session_id`, checar se ela já está em andamento (dicionário em memória é suficiente, ex: `{session_id: {"status": ..., "processed": N, "total": M}}`). Se já existir com `status: "in_progress"`, responder **409** imediatamente em vez de iniciar um segundo processamento concorrente — é a causa raiz do incidente mais recente (duas execuções processando a mesma sessão ao mesmo tempo, sobrecarregando o serviço e corrompendo a contagem).

### Processamento em background thread, não bloqueando o event loop

Como o `model.transcribe()` é uma chamada síncrona e pesada de CPU, rodá-la direto numa rota `async def` do FastAPI bloquearia o event loop inteiro — inclusive as chamadas a `/status` e `/health`, que precisam continuar respondendo durante o processamento. Rodar o loop de transcrição da sessão numa thread separada (`threading.Thread` ou `concurrent.futures.ThreadPoolExecutor` com 1 worker, pra manter o processamento serializado como já era) resolve isso.

### Callback com retry

Se o `POST` pro `callback_url` falhar (n8n reiniciando bem na hora, por exemplo), tentar novamente com backoff (3 tentativas). Se persistir, registrar no log — o `/status` continua consultável manualmente como fallback.

## Restrições

- Status em memória, não persiste — se o processo do `whisper-service` reiniciar no meio de uma sessão, o progresso daquela sessão se perde do `/status` (o `transcricao.txt` parcial, se algo já tiver sido escrito, também se perde, já que a escrita acontece só no final do lote inteiro). Aceitável nesta fase; se virar problema recorrente, uma evolução futura seria escrever incrementalmente e persistir o status em arquivo/SQLite em vez de memória.
- Ainda um único worker/processo — duas sessões diferentes (não a mesma, o caso já tratado) rodando ao mesmo tempo ainda disputariam a mesma CPU limitada (`WHISPER_CPU_THREADS`), mas isso é esperado e aceitável — não é o bug que estamos corrigindo aqui.

## Critérios de aceite

- `POST /transcribe-session` responde em menos de 1s (não espera o processamento).
- Uma segunda chamada pra mesma `session_id` enquanto a primeira roda retorna 409, não inicia um segundo processamento.
- `GET /status/{session_id}` reflete progresso incremental real durante o processamento (não só 0% ou 100%).
- Ao final, o callback chega no `callback_url` com os dados corretos, e o `transcricao.txt` gerado bate com o formato que o n8n já esperava (mesmo `[HH:MM:SS] Nome: texto` de antes).
- Servidor (`/health`) continua respondendo normalmente durante o processamento de uma sessão inteira.