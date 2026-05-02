import os
import re
import requests
from flask import Flask, request, redirect

app = Flask(__name__)

# Suas listas originais
LISTAS_M3U = [
    "https://github.com/StartStatic1/meus-apks/releases/download/V_backup/lista.m3u",
    "https://github.com/StartStatic1/meus-apks/releases/download/V_BACKUP2/lista2.m3u"
]

# Dicionário na memória: Guarda o nome do filme e TODOS os links associados a ele
catalogo_filmes = {}

def limpar_texto(texto):
    """Limpa o nome arrancando anos (1997), tags HD, FHD, legendado, etc."""
    t = re.sub(r'\[.*?\]|\(.*?\)', '', str(texto))
    t = re.sub(r'(?i)(1080p|720p|4k|fhd|hd|dual|dublado|legendado)', '', t)
    t = re.sub(r'[^a-zA-Z0-9\s]', '', t)
    return " ".join(t.split()).lower()

def carregar_m3u():
    global catalogo_filmes
    catalogo_filmes = {}
    print("🚀 Iniciando Motor VIP e filtrando listas...")
    
    for url in LISTAS_M3U:
        try:
            r = requests.get(url, stream=True, timeout=30)
            linhas = [l.decode('utf-8', errors='ignore').strip() for l in r.iter_lines() if l]
            
            for i in range(len(linhas)):
                if linhas[i].startswith("#EXTINF"):
                    # Pega o nome do filme e limpa toda a sujeira
                    nome_sujo = linhas[i].split(",")[-1]
                    nome_limpo = limpar_texto(nome_sujo)
                    
                    if i + 1 < len(linhas):
                        link = linhas[i+1]
                        if "movie" in link or ".mp4" in link or ".mkv" in link:
                            # Se o filme não existe no dicionário, cria uma lista pra ele
                            if nome_limpo not in catalogo_filmes:
                                catalogo_filmes[nome_limpo] = []
                            # Adiciona o link na lista de opções daquele filme
                            catalogo_filmes[nome_limpo].append(link)
        except Exception as e:
            print(f"Erro ao carregar lista {url}: {e}")
            
    print(f"✅ Catálogo pronto! {len(catalogo_filmes)} títulos únicos na memória.")

# Carrega as listas assim que o servidor ligar
carregar_m3u()

def buscar_sniper_vip(titulo):
    titulo_busca = limpar_texto(titulo)
    links_encontrados = []
    
    # 1. Busca Direta
    if titulo_busca in catalogo_filmes:
        links_encontrados = catalogo_filmes[titulo_busca]
    else:
        # 2. Busca por contenção (se o nome estiver no meio de outras palavras)
        for nome_cat, links in catalogo_filmes.items():
            if titulo_busca in nome_cat:
                links_encontrados.extend(links)

    if not links_encontrados:
        return None

    # ===============================================================
    # 🔥 A MÁGICA: SISTEMA DE PRIORIDADE DE SERVIDORES (VIP vs LIXO)
    # ===============================================================
    link_vip = None
    link_secundario = None

    for link in links_encontrados:
        # SE TIVER IP PREMIUM, SERV99 OU O NOVO MASTER99999, É VIP! CAPTURA NA HORA.
        if "209.131.122.80" in link or "serv99" in link or "master99999" in link:
            link_vip = link
            break # Achamos o ouro absoluto, para de procurar!
            
        # Se for o fontedecanais, a gente guarda só se não tiver NENHUMA outra opção
        elif "fontedecanais" in link:
            if not link_secundario:
                link_secundario = link
        
        # Qualquer outro link aleatório ganha do fontedecanais
        else:
            link_secundario = link

    # O sistema sempre devolve o VIP primeiro.
    return link_vip if link_vip else link_secundario

@app.route("/buscar")
def buscar():
    titulo = request.args.get("titulo", "")
    if not titulo:
        return "Título não fornecido", 400
        
    link = buscar_sniper_vip(titulo)
    
    if link:
        # Redireciona o site direto pro MP4 bom
        return redirect(link)
    else:
        return "Filme indisponível nos servidores.", 404

@app.route("/")
def index():
    return f"🚀 Motor Cine Mega VIP Online! | Títulos Indexados: {len(catalogo_filmes)}", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
