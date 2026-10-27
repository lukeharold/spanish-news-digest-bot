# Google News fallback for outlets without a working RSS feed of their own
def google_news(site):
    return f"https://news.google.com/rss/search?q=site:{site}+when:7d&hl=es-419&gl=MX&ceid=MX:es-419"


FEEDS = {
    # Tijuana / Border Region
    "Zeta Tijuana":              "https://zetatijuana.com/feed/",
    "El Mexicano":               google_news("el-mexicano.com.mx"),
    "El Imparcial":              "https://www.elimparcial.com/arc/outboundfeeds/rss/?outputType=xml",
    "Tijuana Press":             "https://tijuanapress.com/feed/",
    "La Voz de la Frontera":     "https://www.lavozdelafrontera.com.mx/rss.xml",
    "Proyecto Puente":           "https://proyectopuente.com.mx/feed/",
    "Uniradio Informa":          "https://www.uniradioinforma.com/feed/",
    "La Jornada Baja California": "https://jornadabc.com.mx/feed/",

    # Latin America
    "BBC Mundo":                 "https://feeds.bbci.co.uk/mundo/rss.xml",
    "El País América":           "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/america/portada",
    "Infobae América":           "https://www.infobae.com/arc/outboundfeeds/rss/category/america/?outputType=xml",
    "La Jornada":                "https://www.jornada.com.mx/rss/edicion.xml?v=1",
    "Animal Político":           google_news("animalpolitico.com"),
    "Eje Central":               google_news("ejecentral.com.mx"),
    "El Tiempo":                 "https://www.eltiempo.com/rss/mundo_latinoamerica.xml",
}
