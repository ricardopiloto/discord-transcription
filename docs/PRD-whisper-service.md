---
document: Product Brief
project: whisper-service (microserviço de transcrição do Cronista)
autor: Mary (PO Virtual) + Ricardo
data: 2026-07-12
escopo: microserviço HTTP local que expõe o faster-whisper para o workflow do n8n
---

# PRD — whisper-service (microserviço de transcrição)

## 1. Problem statement

O workflow "Cronista - Transcrição da Sessão" (n8n) precisa transcrever dezenas de arquivos de áudio curtos (utterances) por sessão. Chamar o `faster-whisper` via linha de comando pra cada arquivo recarregaria o modelo do zero a cada chamada — caro e lento, considerando o volume de arquivos numa sessão de 3-4h. É necessário um processo que carregue o modelo **uma única vez** e fique disponível pra receber chamadas repetidas, rápido o suficiente para não virar o gargalo do pipeline.

## 2. Proposta e escopo do MVP

Um microserviço HTTP (FastAPI) rodando localmente no mesmo servidor do Cronista e do n8n, que recebe um caminho de arquivo de áudio e devolve o texto transcrito. Já existe uma primeira versão funcional (`main.py`) — este PRD formaliza os requisitos pra você desenvolver/revisar na sua máquina antes de portar pro servidor.

### Funcionalidades incluídas

| # | Funcionalidade | Descrição |
|---|---|---|
| F1 | `POST /transcribe` | Recebe `{audio_path, language}`, devolve `{text, language, duration_s}` |
| F2 | `GET /health` | Retorna status do serviço e qual modelo está carregado — usado pelo seu cron de monitoramento existente |
| F3 | Carregamento único do modelo | Modelo carregado na inicialização do processo, não a cada chamada |
| F4 | Configuração via variáveis de ambiente | Tamanho do modelo e tipo de computação ajustáveis sem alterar código |

### Fora de escopo

- Upload de arquivo binário via HTTP (o serviço só recebe um *caminho* de arquivo já presente em disco — mais simples e mais rápido, já que tudo roda no mesmo host)
- Fila de processamento / múltiplos workers concorrentes (ver seção 4.4)
- Interface web
- Suporte a GPU nesta fase (fica como evolução futura se você seguir com a ideia da RTX 3060)

## 3. Usuários e caso de uso

**Usuário:** exclusivamente o workflow "Cronista - Transcrição da Sessão" no n8n, via chamada HTTP interna. Não é um serviço voltado a pessoas nem exposto publicamente.

**Caso de uso:** para cada utterance listada no `speaking_log.jsonl` de uma sessão, o n8n chama `/transcribe` passando o caminho do `.ogg`, recebe o texto de volta, e segue pra montagem do transcript final.

## 4. Especificação técnica

### 4.1 Stack

- Python 3.11+, `fastapi`, `uvicorn`, `faster-whisper` (CTranslate2 — já justificado nas conversas anteriores: mesma qualidade do Whisper original, mais leve em CPU)
- Deploy final: systemd, mesmo padrão do Bertroldo e do Cronista (venv próprio, usuário `adminvtt`)

### 4.2 Contrato da API

**`POST /transcribe`**

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

Response (500) — falha na transcrição (arquivo corrompido, formato inválido, etc.):
```json
{ "detail": "mensagem do erro original" }
```

**`GET /health`**

```json
{ "status": "ok", "model": "small", "compute_type": "int8" }
```

### 4.3 Configuração (variáveis de ambiente)

| Variável | Default | Descrição |
|---|---|---|
| `WHISPER_MODEL_SIZE` | `small` | `tiny`/`base`/`small`/`medium`/`large-v3` — trade-off velocidade x qualidade, testar na prática com transcrições reais de sessão |
| `WHISPER_COMPUTE_TYPE` | `int8` | quantização — `int8` é o mais leve pra CPU |
| `WHISPER_HOST` | `0.0.0.0` | ver seção 4.4 — não pode ser `127.0.0.1` |
| `WHISPER_PORT` | `8008` | porta do serviço |

### 4.4 Rede: alcance a partir do container do n8n (correção importante)

O n8n roda em Docker; o `whisper-service` roda direto no host (fora de container, como o Bertroldo). Isso tem uma implicação de rede que eu errei ao especificar antes:

- **O serviço precisa escutar em `0.0.0.0`, não em `127.0.0.1`.** Um bind em `127.0.0.1` só aceita conexões que se originam do próprio processo/máquina local via loopback — tráfego vindo da interface bridge do Docker (que é como o container do n8n vai alcançar o host) não é tratado como loopback e seria recusado.
- **O n8n deve chamar via `host.docker.internal`, não `127.0.0.1`.** Em Docker no Linux (diferente do Docker Desktop no Mac/Windows, onde isso já vem pronto), é preciso declarar isso explicitamente no `docker-compose.yml` do n8n:

```yaml
services:
  n8n:
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

- **URL a corrigir no node "Transcrever utterance (Whisper)"** do workflow já entregue: trocar `http://127.0.0.1:8008/transcribe` por `http://host.docker.internal:8008/transcribe`.
- **Risco de segurança:** escutar em `0.0.0.0` expõe o serviço pra qualquer coisa que alcance essa porta no host, não só o Docker — incluindo, em teoria, a rede local (LAN) se não houver firewall bloqueando. Como esse serviço não tem autenticação (não foi pensado pra ser exposto), recomendo uma regra de firewall (`ufw`) restringindo a porta `8008` a conexões vindas da sub-rede da bridge do Docker (tipicamente `172.17.0.0/16`, mas confirme com `docker network inspect bridge` no seu servidor) e do próprio `localhost` — nunca liberando pra rede local inteira.

### 4.5 Concorrência

O n8n, do jeito que o workflow foi desenhado, chama `/transcribe` sequencialmente (uma utterance de cada vez), então não há chamadas paralelas na prática hoje. Ainda assim, vale rodar o `uvicorn` com um único worker (`--workers 1`) nesta fase — como o modelo do faster-whisper é carregado uma vez em memória e reutilizado a cada chamada, múltiplos workers duplicariam o uso de RAM (um modelo carregado por worker) sem necessidade, já que não há paralelismo real sendo explorado agora.

### 4.6 Testes locais (na sua máquina, antes de portar pro servidor)

Como você vai desenvolver localmente, sem o Docker/n8n do servidor por perto:

1. Suba o serviço local (`uvicorn main:app --host 0.0.0.0 --port 8008 --reload` pra hot-reload durante o dev).
2. Teste com `curl` direto, sem precisar do n8n:
   ```bash
   curl -X POST http://localhost:8008/transcribe \
     -H "Content-Type: application/json" \
     -d '{"audio_path": "/caminho/local/teste.ogg", "language": "pt"}'
   ```
3. Só depois de validar a qualidade da transcrição com um áudio real da campanha (idealmente um trecho curto gravado pelo Cronista) é que vale portar pro servidor e testar a integração de rede via Docker (seção 4.4).

## 5. Métricas de sucesso

- `/health` responde consistentemente depois do processo subir (confirma que o modelo carregou sem erro).
- Uma utterance de ~10-15s transcreve em tempo bem menor que sua duração real (não precisa ser tempo real, mas não pode ser um gargalo que trave o pipeline por horas).
- Texto transcrito reconhece nomes próprios da campanha (PJs, lugares) numa taxa aceitável — validar com um teste real antes de assumir que o modelo `small` é suficiente; se a qualidade for ruim, subir pra `medium` é só trocar a variável de ambiente.
- Depois de portado pro servidor: o n8n consegue alcançar o serviço via `host.docker.internal` sem erro de conexão.

## 6. Restrições, não-objetivos e perguntas em aberto

### Restrições
- CPU-only nesta fase (Kron Mini K1 sem GPU dedicada).
- Sem autenticação — depende inteiramente de estar isolado por rede/firewall, não por token. Se algum dia esse serviço precisar ser alcançado por algo fora do host, isso precisa ser revisitado.

### Não-objetivos
- Diarização — já resolvida pela segmentação por usuário do Cronista.
- Tradução — sempre transcreve no idioma informado (`pt` por padrão).
- Processamento em GPU — fica pra uma fase futura, se a compra de hardware acontecer.

### Perguntas em aberto
1. **Tamanho de modelo definitivo** — `small` é o ponto de partida, mas só um teste real com áudio da campanha (nomes de personagens, jargão de WFRP) vai dizer se compensa subir pra `medium` em troca de mais tempo de processamento.
2. **Regra de firewall exata** — qual sub-rede da bridge Docker do seu servidor específico (confirmar com `docker network inspect bridge` antes de escrever a regra do `ufw`).
3. **Vale um timeout/circuit breaker** no lado do n8n caso o `whisper-service` trave numa utterance específica (ex: arquivo corrompido) e não retorne? Hoje o node HTTP Request já tem um timeout de 120s configurado, mas vale confirmar se isso é suficiente ou se precisa de tratamento de erro mais explícito no workflow.
