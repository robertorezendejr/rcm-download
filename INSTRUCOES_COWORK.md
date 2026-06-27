# Briefing para o Claude Cowork — finalizar a automação RCM

> Cole este arquivo inteiro como prompt para o Claude Cowork (que tem acesso à
> máquina e pode concluir o login Microsoft/MFA na janela do navegador).

---

## Contexto

Projeto em **Python + Playwright** que automatiza o download do relatório **RCM**
do sistema interno **https://mio.app.br/**, autenticando via **Microsoft**.
O projeto fica em:

```
/Users/robertorezendejr/Documents/www/RCM-Download
```

O ambiente **já está montado**: existe um virtualenv em `.venv` com `playwright`,
`python-dotenv` e `rich` instalados, e o canal `msedge` (Microsoft Edge) já
integrado ao Playwright. Para rodar qualquer coisa use **sempre** o Python do venv:

```bash
cd /Users/robertorezendejr/Documents/www/RCM-Download
./.venv/bin/python <arquivo.py>
```

Estrutura relevante:

```
main.py                 # orquestra: login -> navegação -> filtros -> download
config.json             # parâmetros (url, tipo, contrato, contrato_uop, portfolio)
.env                    # EMAIL e PASSWORD (já preenchidos)
tools/inspecionar.py    # FERRAMENTA p/ descobrir seletores reais (use bastante)
modules/
  browser.py            # abre o Edge (channel="msedge") e salva storage_state.json
  login.py              # cookies + Microsoft  -> JÁ VALIDADO com a tela real
  navegacao.py          # menu -> Suprimentos -> RCM   -> SELETORES A CONFIRMAR
  download.py           # 4 filtros + Exportar Excel    -> SELETORES A CONFIRMAR
  utils.py / config.py / logger.py / progress.py
```

## O que JÁ está pronto e validado

- O robô **abre o Edge sozinho** e navega até `https://mio.app.br/`.
- A **tela de login real** foi inspecionada e os seletores corrigidos em
  `modules/login.py`:
  - Cookies = link com texto **"Aceito / I Agree"** (precisa aceitar para o
    botão Microsoft aparecer).
  - Botão Microsoft = `#btn_microsoft`.
  - (campos locais, caso precise: usuário `#inputText`, senha `#inputPassword`.)
- Login Microsoft (e-mail → conta corporativa → senha → "Continuar conectado?")
  usa os seletores padrão da Microsoft, já implementados.
- Sessão é persistida em `storage_state.json` (próximos acessos não pedem login).

## O que FALTA fazer (sua tarefa)

Eu (assistente anterior) **não consegui passar do login** porque exige **MFA**
(aprovação no app/celular), que só um humano na máquina conclui. Portanto, tudo
**depois do login** ainda usa seletores genéricos e precisa ser confirmado com a
interface real:

1. **Expandir o menu lateral** e clicar em **Suprimentos** → `modules/navegacao.py`
2. **Clicar no botão verde RCM** → `modules/navegacao.py`
3. Preencher **4 listas suspensas** → `modules/download.py`:
   - **Tipo** = `Detalhado`
   - **Contrato** = `UOBS_2025`
   - **Contrato/UO/Plat** = `UOBS_2025 - P-68 - PETROBRAS - EDISE`
   - **Portfólio** = `P68-2026-PP`
     (os valores vêm de `config.json`; não troque os valores, só os seletores)
4. Clicar em **Exportar Excel** e salvar o download em
   `downloads/RCM_AAAA-MM-DD_HH-MM.xlsx` (a lógica de salvar já existe).

## Procedimento recomendado (passo a passo)

1. **Abra o inspetor e faça o login (uma vez):**

   ```bash
   cd /Users/robertorezendejr/Documents/www/RCM-Download
   ./.venv/bin/python tools/inspecionar.py
   ```

   - O Edge abre. **Conclua o login Microsoft + MFA na janela.**
   - Quando o sistema carregar, volte ao terminal e **pressione ENTER** para
     listar os elementos da tela. Anote `id` / texto / `aria-label`.

2. **Navegue manualmente** (na janela) até cada tela — menu expandido,
   Suprimentos, RCM, tela do relatório — e a cada tela **pressione ENTER** no
   terminal para capturar os seletores reais daquela tela.
   - Para as listas suspensas: abra cada uma e pressione ENTER para ver se as
     opções viram `[role=option]`, `<li>`, ou itens de `<select>`.

3. **Atualize os seletores** com base no que descobriu:
   - `modules/navegacao.py` → métodos `_expand_menu`, `open_suprimentos`, `open_rcm`.
   - `modules/download.py` → métodos `_find_field`, `_pick_option`, `export_excel`.
   - **Prioridade de seletor:** `id` > `get_by_role`/`get_by_label` >
     `get_by_text`/`get_by_placeholder` > CSS. **Evite XPath e nunca use
     coordenadas/pixels.**
   - Saia do inspetor com `q` + ENTER (a sessão fica salva).

4. **Rode o fluxo completo de ponta a ponta:**
   ```bash
   ./.venv/bin/python main.py
   ```
   Como a sessão já está salva, ele deve entrar direto, navegar, filtrar e baixar.

## Critério de sucesso

- `./.venv/bin/python main.py` termina com `✔ Download concluído` e gera um
  arquivo `downloads/RCM_AAAA-MM-DD_HH-MM.xlsx` **válido** (abre no Excel com os
  dados do relatório filtrado).
- Em caso de erro, há screenshot automático em `logs/screenshots/` e log em
  `logs/log.txt` — use-os para depurar.

## Regras (não violar)

- **Nada de coordenadas de tela, PyAutoGUI ou localização por pixels.**
- Localizar elementos por **texto, id, name, placeholder, aria-label, role**;
  CSS quando necessário; XPath só em último caso.
- **Senha só via `.env`** — nunca escreva credenciais no código.
- Mudanças **cirúrgicas**: altere apenas os seletores que precisarem; não
  refatore o que já funciona.
- Mantenha **type hints** e funções pequenas (o projeto segue esse padrão).

## Comandos úteis (resumo)

```bash
cd /Users/robertorezendejr/Documents/www/RCM-Download

# inspecionar seletores (faz login na 1ª vez)
./.venv/bin/python tools/inspecionar.py

# rodar o fluxo completo
./.venv/bin/python main.py

# forçar novo login (se a sessão expirar)
rm -f storage_state.json

# depurar passo a passo com o Inspector do Playwright
PWDEBUG=1 ./.venv/bin/python main.py
```

/Users/robertorezendejr/Documents/www/RCM-Download
