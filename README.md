# AURA

Assistente pessoal local para Windows: voz, chat, memória, visão de tela, leitura/edição de documentos
e um Centro de Comando com agenda, e-mails, notícias e briefing matinal. Roda 100% na sua máquina com
[Ollama](https://ollama.com) — nenhum dado sai para APIs pagas.

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.13, FastAPI, WebSocket (`src/aura`) |
| Interface | React 19 + Vite (`ui/`), janela nativa via pywebview |
| LLM | Ollama (`llama3.2:3b` chat, `qwen2.5-coder:3b` código, `moondream` visão) |
| Voz | faster-whisper (STT), Piper / pyttsx3 (TTS) |
| Antena | Node.js (`antenna/server.js`, porta 4242) — proxy iCal/RSS + IMAP Gmail |

## Instalação

```powershell
py -3.13 -m pip install -e ".[dev]"
cd ui; npm install; npm run build; cd ..
ollama pull llama3.2:3b; ollama pull qwen2.5-coder:3b; ollama pull moondream
```

Voz Piper (opcional, 63 MB, fora do git): baixe `pt_BR-faber-medium.onnx` e `.onnx.json` de
[rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices/tree/main/pt/pt_BR/faber/medium)
para `assets/voices/`.

## Uso

```powershell
scripts\launch-aura.bat          # abre a AURA em http://127.0.0.1:8765
node antenna\server.js           # antena para agenda, e-mails e notícias
```

`AURA_DATA` define onde ficam memória, histórico e logs (padrão do launcher: `D:/AURA/data`).
Ajustes pessoais vão em `config/local.json` (ignorado pelo git), sobrepondo `config/default.json`.

### Centro de Comando

Configure na aba ⚙ do painel (dados ficam só no `localStorage` do navegador):

- **Agenda**: link iCal secreto do Google Agenda (suporta eventos recorrentes).
- **Gmail**: e-mail + [senha de app](https://myaccount.google.com/apppasswords).

### Comandos de voz rápidos (respondidos sem LLM)

| Diga | Resposta |
|---|---|
| `bom dia` | briefing matinal falado (clima, agenda, e-mails, notícias) |
| `minha agenda` / `agenda da semana` | eventos de hoje / da semana |
| `próximo compromisso` | próximo evento com contagem regressiva |
| `meus e-mails` / `tem e-mail importante?` | resumo da triagem AÇÃO / INFO / RUÍDO |
| `notícias` | manchetes por tema |
| `atualiza briefing` | recarrega os painéis |

Qualquer outra frase vai para o modelo normalmente.

## Testes

```powershell
py -3.13 -m pytest -q -m "not slow"   # rápidos
py -3.13 -m pytest -q -m slow         # exigem Ollama rodando
```
