import os
import json
import anthropic
import feedparser
from pathlib import Path
from datetime import date

FEEDS = {
    "Google Developers": "https://developers.googleblog.com/feeds/posts/default",
    "TechCrunch": "https://techcrunch.com/feed/",
    "Real Python": "https://realpython.com/atom.xml",
    "Python Insider": "https://blog.python.org/feeds/posts/default",
    "Hacker News": "https://hnrss.org/frontpage",
}

PALAVRAS_CHAVE = [
    "python", "ia", "ai", "llm", "automação", "automation",
    "api", "machine learning", "data", "dados", "agent", "open source", 
    "linux", "claude-code", "clean-code", "java", "IoT"
]

QUANTIDADE_POSTS = 3          # quantos rascunhos gerar por dia
MODELO = "claude-sonnet-5-5"  # troque se quiser outro modelo
PASTA_SAIDA = Path("rascunhos")
ARQUIVO_USADOS = Path("usados.json")  # evita repetir notícias
# ------------------------------------------------------------

PROMPT = """Você é um criador de conteúdo técnico para LinkedIn, escrevendo em português do Brasil e em inglês para postagens bílingue.

Com base na notícia abaixo, escreva um post para o LinkedIn seguindo estas regras:
- Primeira linha: um gancho curto que faça a pessoa clicar em "ver mais".
- Explique a novidade com as SUAS palavras, em 3 a 5 parágrafos curtos. Não copie trechos do original.
- Mostre por que isso importa para quem programa em Python.
- Inclua um mini exemplo de código Python (até 12 linhas) relacionado ao tema, dentro de um bloco de código. Pode ser código usando a linguagem que a notícia apresenta também - o importante É NUNCA DEIXAR DE MOSTRAR CÓDIGO QUANDO POSSÍVEL
- Termine com uma pergunta que incentive comentários.
- Tom: próximo, direto, sem exagero de emojis (no máximo 2).
- Cite a fonte com o link no final.
- Termine com 3 a 4 hashtags.
- Se a notícia não tiver relação clara com programação, crie o ângulo mais útil possível para devs, sem inventar fatos.
- Crie uma versão em inglês e deixe o número de caracteres dentro do limite permitido pelo LinkedIn.

Título: {titulo}
Fonte: {fonte}
Link: {link}
Resumo: {resumo}
"""


def carregar_usados() -> set:
    if ARQUIVO_USADOS.exists():
        return set(json.loads(ARQUIVO_USADOS.read_text(encoding="utf-8")))
    return set()


def salvar_usados(usados: set) -> None:
    ARQUIVO_USADOS.write_text(
        json.dumps(sorted(usados), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def pontuar(titulo: str, resumo: str) -> int:
    """Conta quantas palavras-chave aparecem no texto (título vale o dobro)."""
    t, r = titulo.lower(), resumo.lower()
    return sum(2 * (p in t) + (p in r) for p in PALAVRAS_CHAVE)


def coletar_noticias(usados: set) -> list[dict]:
    noticias = []
    for fonte, url in FEEDS.items():
        feed = feedparser.parse(url)
        if not feed.entries:
            print(f"[aviso] Sem itens em '{fonte}'. Verifique a URL do feed: {url}")
            continue
        for e in feed.entries[:15]:
            link = e.get("link", "")
            if not link or link in usados:
                continue
            titulo = e.get("title", "")
            resumo = e.get("summary", "")[:800]
            noticias.append(
                {
                    "fonte": fonte,
                    "titulo": titulo,
                    "link": link,
                    "resumo": resumo,
                    "pontos": pontuar(titulo, resumo),
                }
            )
    noticias.sort(key=lambda n: n["pontos"], reverse=True)
    return noticias


def gerar_rascunho(client: anthropic.Anthropic, noticia: dict) -> str:
    resposta = client.messages.create(
        model=MODELO,
        max_tokens=2000,
        messages=[
            {
                "role": "user",
                "content": PROMPT.format(
                    titulo=noticia["titulo"],
                    fonte=noticia["fonte"],
                    link=noticia["link"],
                    resumo=noticia["resumo"],
                ),
            }
        ],
    )
    for block in resposta.content:
        if block.type == "text":
            return block.text
    return ""


def main() -> None:
    usados = carregar_usados()
    noticias = coletar_noticias(usados)
    escolhidas = [n for n in noticias if n["pontos"] > 0][:QUANTIDADE_POSTS]

    if not escolhidas:
        print("Nenhuma notícia relevante encontrada hoje.")
        return

    client = anthropic.Anthropic()  # lê ANTHROPIC_API_KEY do ambiente
    PASTA_SAIDA.mkdir(exist_ok=True)
    arquivo = PASTA_SAIDA / f"{date.today().isoformat()}.md"

    with arquivo.open("w", encoding="utf-8") as f:
        f.write(f"# Rascunhos de {date.today().strftime('%d/%m/%Y')}\n\n")
        for i, n in enumerate(escolhidas, 1):
            print(f"Gerando rascunho {i}/{len(escolhidas)}: {n['titulo']}")
            texto = gerar_rascunho(client, n)
            f.write(f"## Opção {i}: {n['titulo']}\n")
            f.write(f"*Fonte: {n['fonte']} — {n['link']}*\n\n")
            f.write(texto + "\n\n---\n\n")
            usados.add(n["link"])

    salvar_usados(usados)
    print(f"\nPronto! Rascunhos salvos em: {arquivo}")


if __name__ == "__main__":
    main()