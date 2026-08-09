# Demanda — Recuperação automática de falhas de decriptação DAVE (Cronista)

## Contexto

Na sessão de 07/08, a conexão de voz sofreu um fechamento anormal (WebSocket 1006) por volta dos 50 minutos. O reconnect automático do py-cord restabeleceu a conexão, mas as chaves de decriptação DAVE não foram renegociadas corretamente — todo pacote de áudio recebido a partir daí falhou (`CryptoError: Decryption failed`), silenciosamente, sem derrubar o bot nem a detecção de fim de sessão. Resultado: mais de 2 horas de sessão real sem nenhum áudio capturado, sem alerta na hora.

Essa classe de bug tende a se repetir — o protocolo DAVE renegocia chaves não só em reconexões do bot, mas toda vez que a lista de participantes do canal muda (alguém cai e volta, por exemplo), o que é comum numa sessão de 6 jogadores e 3+ horas.

## Objetivo

Detectar essa falha em tempo real (não no dia seguinte, analisando log) e recuperar automaticamente via reconexão completa do canal, já que o reconnect "leve" da lib comprovadamente não resolve.

## Comportamento esperado

### Detecção

- Monitorar exceções de decriptação (`CryptoError`/erros de decodificação de pacote de voz) por conexão de voz ativa.
- Manter um contador de falhas consecutivas; resetar o contador a cada pacote decodificado com sucesso.
- Dispara ação de recuperação ao atingir um threshold configurável (falhas consecutivas dentro de uma janela de tempo curta — uma falha isolada pode ser ruído de rede, uma sequência é sinal de chave quebrada).

### Recuperação

- Ao disparar: desconectar **completamente** do canal de voz (`voice_client.disconnect()`) e reconectar do zero (`channel.connect()`) — não usar o reconnect interno da lib, já que ele foi o que falhou em restabelecer as chaves na sessão de 07/08.
- Se a reconexão falhar, tentar novamente com backoff, até um limite de tentativas configurável.
- A gravação em andamento (utterances já fechadas antes da falha) permanece intacta — a recuperação só afeta a captura a partir do momento da falha em diante.

### Registro do gap

- Registrar cada intervalo sem captura num arquivo dedicado (`recording_gaps.jsonl`, mesmo padrão de linha-JSON do `speaking_log.jsonl`), com pelo menos: horário de início do gap, horário de fim (quando a reconexão for bem-sucedida), motivo (`dave_decrypt_failure`), número de tentativas até reconectar, e se teve sucesso.
- Isso existe pra que o pipeline de transcrição (e qualquer análise futura) saiba que houve um buraco real, em vez de interpretar ausência de dados como "ninguém falou nesse intervalo" — foi exatamente a falta dessa informação que tornou o diagnóstico de 07/08 demorado.

### Alerta

- Notificação via Telegram (reaproveitando o bot de monitoração já existente) assim que o gap for detectado — não esperar o fim da sessão:
  - Ao detectar: `⚠️ Cronista: falha de decriptação DAVE detectada no canal {channel}, tentando reconectar...`
  - Ao recuperar: `✅ Reconexão bem-sucedida, gravação retomada após {duração_do_gap}`
  - Se esgotar as tentativas sem sucesso: `🔴 Falha ao reconectar após {N} tentativas — gravação da sessão comprometida a partir de {horário}`

## Configuração (variáveis de ambiente)

| Variável | Default | Descrição |
|---|---|---|
| `CRONISTA_DAVE_FAILURE_THRESHOLD` | `5` | falhas de decriptação consecutivas pra considerar a chave quebrada |
| `CRONISTA_DAVE_FAILURE_WINDOW_S` | `10` | janela de tempo em que essas falhas precisam ocorrer pra contar como "em sequência" (evita contar falhas espaçadas de minutos como o mesmo incidente) |
| `CRONISTA_RECONNECT_MAX_ATTEMPTS` | `5` | tentativas de reconexão completa antes de desistir e escalar o alerta |
| `CRONISTA_RECONNECT_BACKOFF_S` | `3` | espera entre tentativas de reconexão (multiplicar por tentativa, ex: 3s, 6s, 9s...) |

## Fora de escopo

- Recuperar o áudio perdido durante o gap — impossível, as chaves daquele intervalo específico não existem mais.
- Reimplementar a negociação de chaves do DAVE em nível baixo — a mitigação é forçar a lib a refazer o handshake completo do zero, não tentar corrigir a rotação de chave manualmente.
- Prevenir o WebSocket 1006 em si (instabilidade de rede pontual) — o foco é detectar e recuperar da consequência (chave quebrada), não evitar a causa (rede).

## Critérios de aceite

- Um teste controlado (forçar `voice_client.disconnect()` manualmente durante uma gravação de teste, simulando o cenário) resulta em: detecção do problema, reconexão automática sem intervenção manual, entrada correspondente em `recording_gaps.jsonl`, e as duas notificações no Telegram (detecção + recuperação).
- Depois da reconexão bem-sucedida, novas utterances voltam a aparecer no `speaking_log.jsonl` normalmente.
- Se uma sessão terminar com gaps registrados, isso fica visível no aviso final da sessão (não é uma informação escondida só no arquivo) — vale considerar incluir a contagem de gaps na notificação de "sessão encerrada" que já existe hoje.