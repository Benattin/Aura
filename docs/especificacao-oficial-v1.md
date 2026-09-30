# Especificação Oficial — AURA

Versão: 1.0  
Status: Proposta de produto e arquitetura  
Plataforma inicial: Windows Desktop  
Idioma principal: Português do Brasil

## 1. Propósito

AURA é uma assistente pessoal de inteligência artificial com voz, interface visual futurista e minimalista, memória persistente, ferramentas (skills) e operação contínua no computador do usuário.

O objetivo é oferecer uma experiência semelhante a uma assistente de voz moderna: a AURA permanece disponível em segundo plano, é ativada pela palavra-chave “Aura”, entende pedidos falados ou escritos, responde rapidamente em texto e voz, executa ações autorizadas e aprende preferências úteis ao longo do tempo.

A AURA não deve fingir ter capacidades que não possui. Ações sensíveis, destrutivas, financeiras, de envio de mensagens, compras, mudanças no sistema ou compartilhamento de dados exigem confirmação explícita do usuário.

## 2. Identidade

- **Nome:** AURA
- **Forma de tratamento do usuário:** Senhor Gustavo, salvo alteração explícita do usuário
- **Personalidade:** Calma, prestativa, objetiva, discreta e natural
- **Idioma padrão:** Português do Brasil
- **Tom:** Claro e direto; explicações maiores apenas quando solicitadas
- **Resposta curta padrão:** Uma confirmação breve antes de executar uma ação, quando aplicável

Exemplos de linguagem:

- “Sim, senhor. Como posso ajudar?”
- “Entendi. Vou pesquisar isso para o senhor.”
- “Encontrei uma opção melhor, mas preciso da sua confirmação antes de alterar o modelo.”
- “Não tenho segurança suficiente para executar essa ação sem confirmação.”

## 3. Objetivos funcionais

A AURA deve:

- Permanecer disponível enquanto o Windows estiver ligado, com baixo consumo de recursos no modo de espera.
- Escutar localmente apenas para detectar a palavra de ativação.
- Ser ativada por “Aura”, “Olá Aura” ou “Hey Aura”.
- Capturar o pedido após a ativação, transcrever a fala e compreender a intenção.
- Responder por voz e pela interface gráfica.
- Consultar modelos de IA locais e, opcionalmente, serviços online escolhidos pelo usuário.
- Executar skills e automações autorizadas.
- Armazenar memória relevante e corrigível pelo usuário.
- Recuperar contexto útil antes de responder.
- Verificar atualizações de modelos, ferramentas e skills conforme política configurada.
- Sugerir uma migração para um modelo melhor quando houver ganho verificável e compatibilidade de hardware.
- Manter logs, controles de privacidade e mecanismos de recuperação em caso de falha.

## 4. Princípios de operação

### 4.1 Privacidade local primeiro

- A detecção da palavra “Aura” deve ser local.
- O áudio contínuo não deve ser gravado por padrão.
- Apenas o trecho posterior à ativação pode ser processado como comando.
- Dados privados, memória e logs devem permanecer locais por padrão.
- Qualquer uso de API externa, nuvem ou compartilhamento deve ser visível nas configurações e controlado pelo usuário.

### 4.2 Rapidez

- O modo de espera deve usar somente o detector de palavra-chave.
- O modelo principal deve permanecer carregado quando o hardware permitir.
- A interface deve continuar responsiva enquanto áudio, IA e skills executam em serviços separados.
- Respostas longas devem ser exibidas e faladas em streaming quando possível.

### 4.3 Segurança por confirmação

A AURA pode executar automaticamente ações reversíveis e de baixo risco, como abrir uma janela de pesquisa ou mostrar informações.

A AURA deve solicitar confirmação explícita antes de:

- Enviar mensagens, e-mails ou publicações.
- Fazer compras, pagamentos ou transferências.
- Apagar arquivos, registros ou memórias.
- Alterar configurações do Windows.
- Instalar aplicativos, modelos ou extensões.
- Baixar modelos grandes ou consumir dados significativos.
- Trocar automaticamente o modelo principal de produção.
- Compartilhar informações pessoais com serviços externos.

### 4.4 Transparência

A AURA deve mostrar na interface:

- Estado atual.
- Modelo ativo.
- Modo de privacidade.
- Uso de memória.
- Última atualização.
- Skills em execução.
- Ações que aguardam confirmação.

## 5. Estados da assistente

A AURA funciona como uma máquina de estados:

| Estado | Descrição | Indicação visual |
| --- | --- | --- |
| Inicializando | Carrega configurações, memória, voz, microfone e modelo | Anel azul com progresso |
| Em espera | Escuta somente a palavra de ativação | Anel discreto azul escuro |
| Ativada | Detectou “Aura” e aguarda o pedido | Anel ciano pulsante |
| Escutando | Captura e transcreve o comando | Onda de áudio ciano |
| Pensando | Recupera memória, consulta modelo e planeja a resposta | Anel violeta girando |
| Executando | Usa uma ou mais skills | Indicador âmbar e lista de ações |
| Falando | Reproduz a resposta por voz | Onda luminosa azul |
| Aguardando confirmação | Uma ação sensível depende de aprovação | Indicador âmbar/vermelho |
| Pausada | Microfone ou automações suspensos pelo usuário | Ícone de pausa |
| Erro | Detectou uma falha e oferece recuperação | Indicador vermelho com detalhe do erro |

## 6. Palavra de ativação

### 6.1 Palavra padrão

A palavra de ativação oficial é “Aura”.

Variações aceitas:

- “Aura”
- “Olá Aura”
- “Hey Aura”

### 6.2 Fluxo de ativação

1. A AURA permanece no estado “Em espera”.
2. O detector local monitora o áudio do microfone em pequenos blocos.
3. Ao reconhecer “Aura” com confiança suficiente, a AURA muda para “Ativada”.
4. A AURA emite um sinal curto e opcionalmente diz: “Sim, senhor?”
5. A AURA captura o comando até detectar silêncio, término de frase ou uma pausa configurável.
6. A AURA processa o pedido, responde e retorna a “Em espera”.

### 6.3 Prevenção de ativações falsas

- Ajustar limiar de confiança do detector.
- Permitir treinamento/calibração da voz do usuário.
- Usar confirmação em casos ambíguos: “O senhor me chamou?”
- Disponibilizar modo “pressione para falar” como alternativa.
- Oferecer botão de microfone e atalho global de teclado.

## 7. Entrada e saída por voz

### 7.1 Entrada de voz

A transcrição deve:

- Priorizar português do Brasil.
- Exibir texto parcial na interface durante a fala.
- Corrigir pontuação quando possível.
- Preservar a transcrição original no histórico da sessão.
- Informar quando não entender: “Não consegui entender, senhor. Poderia repetir?”

### 7.2 Saída de voz

A voz da AURA deve:

- Ser clara, natural e com velocidade configurável.
- Ter volume, tom e taxa de fala ajustáveis.
- Permitir interrupção quando o usuário disser “Aura, pare” ou falar novamente.
- Evitar falar textos extensos; oferecer resumo falado e detalhes na interface.

### 7.3 Conversa contínua

Após uma solicitação, a AURA pode manter uma janela curta de continuação para perguntas relacionadas, por exemplo, 15 segundos.

Exemplo:

- Usuário: “Aura, pesquise notebooks para programação.”
- AURA: “Encontrei opções. O senhor prefere até qual valor?”
- Usuário: “Até quatro mil reais.”

Durante essa janela, não é necessário repetir a palavra de ativação. Após o tempo configurado, a AURA volta a exigir “Aura”.

## 8. Cérebro de IA

### 8.1 Arquitetura de modelos

A AURA utiliza uma arquitetura de roteamento:

- **Modelo rápido:** responde comandos simples, conversa breve, classificação de intenção e planejamento inicial.
- **Modelo principal:** raciocínio, análise, redação, programação, pesquisa e decisões mais complexas.
- **Modelo especializado opcional:** visão, áudio, código, documentos ou tarefas específicas.

A execução local deve ser priorizada. Serviços externos só entram quando configurados e necessários para uma qualidade, atualização ou capacidade específica.

### 8.2 Perfil de comportamento

O modelo principal recebe regras permanentes:

- Tratar o usuário como “senhor”.
- Responder em português do Brasil, salvo pedido contrário.
- Ser preciso, reconhecer incerteza e não inventar resultados.
- Recuperar memória relevante, mas nunca expor dados pessoais desnecessariamente.
- Planejar ações antes de executar skills.
- Pedir confirmação para ações sensíveis.
- Informar falhas com linguagem simples e oferecer alternativas.

### 8.3 Roteamento de tarefas

A AURA classifica cada pedido em uma categoria:

- Conversa e dúvidas gerais.
- Pesquisa atualizada na internet.
- Programação e análise técnica.
- Organização pessoal e lembretes.
- Controle do computador.
- Música e entretenimento.
- Documentos, arquivos e planilhas.
- Segurança e privacidade.
- Automação por skills.

Pedidos simples devem usar o caminho mais rápido. Pedidos complexos devem recuperar memória, elaborar plano e usar ferramentas adequadas.

## 9. Memória e aprendizagem

### 9.1 Princípio central

A AURA melhora por meio de memória, feedback e revisão de processos, e não por alterar silenciosamente seus próprios pesos de modelo. A troca ou atualização de modelos é uma decisão controlada, testada e aprovada pelo usuário.

### 9.2 Tipos de memória

| Tipo | Conteúdo | Duração |
| --- | --- | --- |
| Contexto de sessão | Últimas mensagens, objetivo atual e tarefas em andamento | Até encerrar ou expirar a sessão |
| Memória episódica | Eventos, conversas relevantes e decisões | Persistente, revisável |
| Memória semântica | Preferências, perfil, fatos estáveis e regras pessoais | Persistente, revisável |
| Memória de procedimentos | Correções, rotinas e formas preferidas de executar tarefas | Persistente, revisável |
| Memória de tarefas | Lembretes, pendências, prazos e estados de automação | Até conclusão ou exclusão |

### 9.3 Armazenamento

A memória deve usar dois níveis:

- Base estruturada local: SQLite ou formato equivalente para preferências, tarefas, configurações e auditoria.
- Índice semântico local: banco vetorial para recuperar trechos relacionados ao pedido atual.

Cada item deve registrar: identificador, conteúdo ou resumo, tipo de memória, data e hora, fonte, nível de confiança, tags, política de retenção, se foi confirmado explicitamente pelo usuário.

### 9.4 Regras para salvar memória

A AURA deve salvar automaticamente apenas informações claramente úteis e de baixo risco, como preferências operacionais e correções diretas.

Exemplos que podem ser salvos:

- “Use o Edge como navegador padrão.”
- “Prefiro respostas diretas.”
- “Estou estudando Sistemas de Informação.”
- “Meu projeto se chama AURA.”

A AURA deve pedir permissão para salvar informações sensíveis ou duradouras, como saúde, finanças, localização detalhada, dados de terceiros e credenciais.

Exemplo: “Senhor, deseja que eu memorize esta preferência para as próximas conversas?”

### 9.5 Consolidação de memória

Em uma rotina programada, a AURA deve:

- Revisar novas interações relevantes.
- Criar resumos curtos e úteis.
- Mesclar memórias duplicadas.
- Reduzir ou remover registros obsoletos conforme política de retenção.
- Nunca excluir dados importantes sem política definida ou confirmação.
- Criar backup local criptografado, se ativado pelo usuário.

### 9.6 Controle do usuário

A interface e a voz devem permitir:

- “Aura, o que você lembra sobre mim?”
- “Aura, esqueça que eu prefiro o Edge.”
- “Aura, não memorize esta conversa.”
- “Aura, exporte minha memória.”
- “Aura, apague toda a minha memória.”

A exclusão total exige confirmação explícita e oferece opção de backup antes da ação.

## 10. Inteligência extrema com governança

A AURA deve buscar a maior qualidade possível dentro do hardware, dos modelos disponíveis e das permissões do usuário. “Inteligência extrema” significa combinar bons modelos, memória, pesquisa, planejamento, ferramentas especializadas, validação e feedback — não executar ações ilimitadas ou sem controle.

### 10.1 Componentes de alta capacidade

- Modelo principal de alta qualidade compatível com o PC.
- Modelo rápido para reduzir latência.
- Recuperação de memória semântica.
- Pesquisa online quando o pedido exigir informação atual.
- Ferramentas especializadas para código, arquivos, planilhas e automação.
- Planejador de tarefas com etapas verificáveis.
- Validador de respostas para checar consistência, segurança e conclusão.
- Registro de erros, correções e melhorias de fluxo.

### 10.2 Processo de raciocínio operacional

Para tarefas complexas, a AURA deve:

1. Identificar objetivo, restrições e nível de risco.
2. Recuperar memória e contexto relevantes.
3. Decidir se precisa de pesquisa ou ferramenta especializada.
4. Elaborar um plano interno de execução.
5. Executar etapas reversíveis e seguras.
6. Pedir confirmação antes de ações irreversíveis ou externas.
7. Verificar o resultado.
8. Responder com o que foi feito, o resultado e próximos passos úteis.
9. Registrar aprendizados ou correções, quando apropriado.

## 11. Atualização e troca de modelos

### 11.1 Princípio

A AURA deve se manter atualizada, mas não deve trocar de modelo automaticamente sem avaliação e aprovação do usuário, pois isso pode consumir armazenamento, processamento, energia e alterar qualidade, privacidade ou comportamento.

A AURA pode baixar modelos de teste somente após confirmação, salvo se o usuário configurar uma política explícita de atualização automática com limites de tamanho e consumo.

### 11.2 Catálogo de modelos

A AURA deve manter um catálogo local com: nome e versão, família, capacidade, tamanho do download, requisitos estimados de RAM/VRAM/CPU/armazenamento, licença, contexto máximo, indicadores de desempenho e qualidade, data da última verificação, fonte de instalação confiável.

### 11.3 Compatibilidade de hardware

Antes de sugerir ou testar um modelo, a AURA verifica: RAM disponível, VRAM (se GPU compatível), espaço livre em disco, temperatura e uso do sistema quando disponíveis, velocidade mínima estimada para voz, compatibilidade com o runtime local.

### 11.4 Critérios de promoção

Um modelo candidato só pode ser recomendado como superior se: for compatível com o hardware; oferecer ganho mensurável de qualidade; mantiver resposta suficientemente rápida para voz; não apresentar regressões relevantes em português, ferramentas ou segurança; tiver origem e licença verificadas.

### 11.5 Bateria de testes

Comparar modelo atual e candidato em: conversa em português; perguntas de estudo de SI; explicação de código Python e Java; planejamento de automações; compreensão de comandos de voz; uso de memória e preferências; chamadas de skills seguras; tempo até a primeira resposta; taxa de erros e alucinações em perguntas verificáveis.

### 11.6 Fluxo de migração

1. Encontra ou recebe informação sobre um modelo candidato.
2. Avalia requisitos e compatibilidade com o PC.
3. Mostra relatório curto: atual, candidato, download, espaço, velocidade e ganhos.
4. Solicita autorização para baixar e testar.
5. Executa testes em perfil temporário, sem apagar o modelo atual.
6. Compara resultados e mostra recomendação.
7. Solicita confirmação para definir o candidato como modelo principal.
8. Mantém o modelo anterior como opção de reversão por período configurável.
9. Registra a troca e permite voltar ao modelo anterior com um comando simples.

### 11.7 Exemplo de notificação

“Senhor, encontrei um modelo compatível que apresentou melhor desempenho em português e programação nos testes locais. O download estimado é de 8 GB e a resposta por voz deve continuar rápida. Deseja que eu faça o teste e apresente o relatório antes de trocar?”

## 12. Skills

### 12.1 Definição

Skills são módulos especializados que permitem à AURA realizar ações no PC ou em serviços autorizados.

Cada skill deve declarar: nome, descrição, parâmetros aceitos, permissões necessárias, nível de risco, ação reversível ou irreversível, método de confirmação exigido, registro de execução.

### 12.2 Skills essenciais

| Skill | Função | Confirmação |
| --- | --- | --- |
| Pesquisa web | Pesquisa informações atuais | Não, salvo envio de dados privados |
| Abrir site | Abre um endereço no navegador | Não |
| Abrir aplicativo | Inicia aplicativo conhecido | Não, salvo aplicativo sensível |
| Arquivos | Localiza, organiza e abre arquivos | Confirmação para mover ou apagar |
| Lembretes | Cria e gerencia lembretes | Não para criar; sim para apagar em lote |
| Calendário | Consulta e cria eventos | Sim antes de criar, editar ou apagar |
| Música | Pesquisa e controla reprodução | Não para reprodução; sim para mudar conta/pagamento |
| Notas | Cria, organiza e pesquisa notas | Não para criar; sim para apagar em lote |
| Planilhas | Lê, analisa e gera relatórios | Sim antes de sobrescrever arquivos |
| Código | Ajuda a criar, revisar e testar projetos | Sim antes de apagar, publicar ou executar comandos perigosos |
| Windows | Consulta status, abre configurações e automatiza tarefas | Sim para mudanças de configuração |
| Atualizações | Verifica modelos e ferramentas | Sim para baixar, instalar ou trocar |

### 12.3 Registro de skills

Toda execução deve registrar: data e hora, skill utilizada, parâmetros relevantes (com ocultação de segredos), resultado, erro se houver, se houve confirmação do usuário.

## 13. Interface visual

### 13.1 Direção visual

Futurista, minimalista e funcional: fundo preto/grafite/azul muito escuro; destaques em ciano, azul elétrico e violeta suave; alto contraste; poucos elementos; animações discretas. Fonte: Segoe UI, Inter ou equivalente.

### 13.2 Tela principal

Cabeçalho (logotipo/nome, status, configurações); núcleo visual (círculo de estado); transcrição; resposta; painel de contexto; ações rápidas; central de confirmação.

### 13.3 Painel de configurações

Microfone e alto-falante; volume, velocidade e voz; palavra de ativação e sensibilidade; modelo rápido e principal; política de atualização; limite de RAM/VRAM; política de memória; integrações e permissões; modo privado; inicialização automática no Windows.

### 13.4 Indicadores obrigatórios

Microfone; palavra de ativação; local ou online; modelo atual; uso estimado de memória/CPU/GPU; última atualização; número de memórias; ações pendentes de confirmação.

## 14. Inicialização automática e disponibilidade

A AURA deve iniciar com o Windows, se o usuário ativar essa opção.

Fluxo: Windows inicia → serviço leve em segundo plano → configurações e detector → UI compacta ou bandeja → modelo principal em segundo plano (limites de hardware) → estado “Em espera”.

Três modos de consumo:

- **Econômico:** detector ativo; modelo principal sob demanda.
- **Equilibrado:** modelo rápido carregado; principal para tarefas complexas.
- **Desempenho máximo:** modelos necessários pré-carregados.

## 15. Pesquisa e atualização de conhecimento

A AURA deve distinguir conhecimento interno do modelo, memória pessoal local e informação atual obtida por pesquisa.

Quando o pedido exigir dados atuais, deve pesquisar e informar fonte e data. Para saúde, direito, finanças e segurança, indicar limitações e recomendar fontes profissionais.

## 16. Segurança e privacidade

### 16.1 Dados sensíveis

Não salvar nem repetir credenciais, senhas, tokens ou chaves privadas. Orientar uso de gerenciador de senhas.

### 16.2 Permissões

Cada integração deve ter permissões mínimas.

### 16.3 Modo privado

Não salvar novas memórias automaticamente; reduzir ou desativar logs de conteúdo; não usar pesquisa ou serviços externos sem confirmação; indicador visual permanente.

### 16.4 Backup e recuperação

Backup local configurável; exportação legível; restauração de versão anterior; criptografia se habilitada.

## 17. Tratamento de falhas

Operar de modo degradado quando possível: sem internet, sem modelo principal, sem microfone, sem voz, skill com erro, modelo lento. Mensagens de erro devem ser úteis e oferecer alternativa.

## 18. Comandos de voz oficiais

Ativação, memória, modelos, PC/produtividade e pesquisa/análise conforme spec 18.1–18.5 (ver documento de origem na conversa e esta seção no Memory Bank).

### 18.1 Ativação e conversa

“Aura.” / “Olá Aura.” / “Aura, como você está?” / “Aura, pare.” / “Aura, entre em modo privado.” / “Aura, volte ao modo normal.”

### 18.2 Memória

“Aura, o que você lembra sobre mim?” / “Aura, memorize que eu prefiro respostas curtas.” / “Aura, esqueça esta preferência.” / “Aura, não memorize esta conversa.” / “Aura, mostre minhas memórias recentes.”

### 18.3 Atualização e modelos

“Aura, qual modelo você está usando?” / “Aura, verificar atualizações de modelo.” / “Aura, compare o modelo atual com o melhor compatível.” / “Aura, teste o novo modelo antes de trocar.” / “Aura, volte para o modelo anterior.”

### 18.4 PC e produtividade

“Aura, abra o Edge.” / “Aura, abra o bloco de notas.” / “Aura, pesquise por vagas de estágio em TI.” / “Aura, crie um lembrete para estudar Python às 20 horas.” / “Aura, organize estes arquivos por tipo.”

### 18.5 Pesquisa e análise

“Aura, pesquise as melhores scooters elétricas dentro do meu orçamento.” / “Aura, compare estes dois produtos.” / “Aura, explique este erro de Python.” / “Aura, analise esta planilha e encontre tendências.”

## 19. Métricas de qualidade

Métricas locais (não saem do PC sem permissão): detecção correta de “Aura”; ativações falsas; tempo ativação→resposta; tempo até primeira palavra falada; entendimento de comandos; sucesso por skill; CPU/RAM/GPU/disco; avaliações do usuário; reversões de modelo.

## 20. Plano de implementação

- **Fase 1 — Base local:** UI básica, wake word, STT pt-BR, TTS, chat com modelo local, histórico de sessão.
- **Fase 2 — Skills essenciais:** pesquisa web, apps/sites, lembretes/notas, Windows básico, central de confirmações.
- **Fase 3 — Memória persistente:** SQLite, RAG, tela de memória, privacidade/backup/exclusão.
- **Fase 4 — Inteligência e automação:** roteamento de modelos, planejamento, validação, skills avançadas.
- **Fase 5 — Atualizações controladas:** catálogo, hardware, testes, migração confirmada, reversão.
- **Fase 6 — Refinamento:** design, latência, voz, expansão de skills.

## 21. Critérios de aceitação

A primeira versão será funcional quando: iniciar no Windows sob escolha do usuário; permanecer em espera detectando “Aura”; transcrever comando em português após ativação; gerar resposta com modelo local; falar e mostrar a resposta; voltar à espera; executar pesquisa web, abertura de app e lembrete; pedir confirmação antes de ações sensíveis; salvar/mostrar/apagar memórias; mostrar modelo ativo e estado atual.

## 22. Visão futura

Plataforma pessoal: núcleo de voz e inteligência + biblioteca de skills, memória confiável, modelos melhores e automações seguras. Valores: rapidez, privacidade e controle humano.
