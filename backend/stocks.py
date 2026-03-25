"""
BIST hisse listesi — BIST30, BIST100, Tüm Hisseler
Yahoo Finance suffix: .IS
"""

BIST30 = [
    "AKBNK", "ARCLK", "ASELS", "BIMAS", "EKGYO", "EREGL", "FROTO",
    "GARAN", "HALKB", "ISCTR", "KCHOL", "KOZAL", "KRDMD", "MGROS",
    "PETKM", "PGSUS", "SAHOL", "SASA", "SISE", "TAVHL", "TCELL",
    "THYAO", "TKFEN", "TOASO", "TTKOM", "TUPRS", "VAKBN", "YKBNK",
    "OYAKC", "SKBNK",
]

_BIST100_EXTRA = [
    # Bankacılık / Finans
    "ALBRK", "ICBCT", "QNBFB", "TSKB", "FINBN",
    # Sigorta / Emeklilik
    "AKGRT", "ANSGR", "AGESA", "TURSG", "RAYSG", "SLNMA",
    # GYO
    "ALGYO", "ISGYO", "NUGYO", "SNGYO", "RYGYO", "VKGYO", "KLGYO",
    "MRGYO", "HLGYO", "ATAGY", "TRGYO", "AGYO", "AKMGY", "BBGYO",
    # Enerji / Elektrik
    "ENERY", "ENJSA", "EUPWR", "ODAS", "ZOREN", "ORGE", "AYEN",
    "ARASE", "AKSEN", "AYDEM", "GOKNR",
    # Havacılık / Lojistik
    "LOGO", "KATMR", "INDES",
    # Perakende / Gıda / İçecek
    "AEFES", "CCOLA", "TATGD", "ULKER", "SOKM",
    # Otomotiv / Makine
    "TTRAK", "DOAS", "KARSN", "BRISA",
    # İnşaat / Çimento
    "NUHCM", "KONYA", "CEMTS", "CIMSA",
    # Holding
    "DOHOL", "GLYHO", "NTHOL",
    # Diğer Sanayi / Kimya
    "GUBRF", "BAGFS", "ALKIM", "PETKM", "ECILC",
    # Teknoloji
    "NETAS",
    # Diğer
    "ASUZU", "BNTAS", "BVSAN", "CATES", "DEVA",
    "EGEEN", "ENKAI", "EPLAS", "FENER", "GEREL",
    "HEKTS", "IPEKE", "JANTS", "KERVT", "KNFRT",
    "KORDS", "KRONT", "KUVVA", "MAVI", "MERCN",
    "NTHOL", "NTTUR", "ONCSM", "OSMEN", "OZSUB",
    "PARSN", "PENTA", "PKENT", "POLHO", "PRKAB",
    "REEDR", "SANKO", "SELEC", "SILVR", "SOKM",
    "SPTEK", "SUMAS", "TKNSA", "TMSN", "TSPOR",
    "TTRAK", "ULUUN", "VAKFN", "WNGAR", "YATAS",
    "YEOTK", "AYES", "BESLR", "AKFEN", "AKSA",
    "ALARK", "ALFEN", "ARSAN", "ASTOR", "ATAKP",
    "AYEN", "BASGZ", "BERA", "BIENY", "BJKAS",
    "BKFIN", "BOBET", "BRYAT", "CANTE", "EGPRO",
    "FMIZP", "GEDZA", "HLGYO", "HTTBT", "ISGSY",
    "KUYAS", "LRSHO", "MEPET", "MIATK", "MIPAZ",
    "OFSYM", "OSTIM", "PAPIL", "PRKME", "ISGYO",
]

_ALL_EXTRA_2 = [
    # BigPara'dan eklenen eksik hisseler (2025)
    "ADGYO", "AGHOL", "AHSGY", "AKENR", "AKFGY", "AKFIS", "AKHAN", "AKSGY", "AKSUE", "AKYHO",
    "ALCTL", "ALKA", "ALKLC", "ALTNY", "ALVES", "ARFYE", "ARMGD", "ARTMS", "ARZUM", "ATATP",
    "ATATR", "ATEKS", "ATLAS", "ATSYH", "AVGYO", "AVHOL", "AVTUR", "BAHKM", "BAKAB", "BALAT",
    "BALSU", "BAYRK", "BEGYO", "BESTE", "BEYAZ", "BIGCH", "BIGEN", "BIGTK", "BINBN", "BINHO",
    "BIOEN", "BLCYT", "BLUME", "BMSCH", "BMSTL", "BOSSA", "BRKSN", "BRLSM", "BRSAN", "BULGS",
    "BYDNR", "CELHA", "CEMAS", "CEMZY", "CGCAM", "CMBTN", "CMENT", "CONSE", "COSMO", "CRDFA",
    "CVKMD", "CWENE", "DAPGM", "DCTTR", "DERHL", "DGATE", "DGGYO", "DIRIT", "DMSAS", "DOFER",
    "DOFRB", "DSTKF", "DUNYH", "DURKN", "DZGYO", "ECOGR", "ECZYT", "EDATA", "EDIP", "EFOR",
    "EGEGY", "EGEPO", "EKIZ", "EKOS", "EKSUN", "ELITE", "EMPAE", "ENDAE", "ENRYA", "ENTRA",
    "ERBOS", "ERCB", "EUKYO", "EUREN", "EUYO", "EYGYO", "FRMPL", "GATEG", "GEDIK", "GENIL",
    "GENKM", "GLDTR", "GLRMK", "GMSTR", "GOLTS", "GOZDE", "GRTHO", "GWIND", "HATEK", "HATSN",
    "HKTM", "HOROZ", "HRKET", "ICUGS", "IHAAS", "INFO", "INGRM", "INTEK", "INVEO", "INVES",
    "ISBTR", "ISGLK", "ISKPL", "ISKUR", "ISMEN", "ISSEN", "IZENR", "IZINV", "KAPLM", "KAREL",
    "KAYSE", "KBORU", "KCAER", "KENT", "KERVN", "KIMMR", "KLMSN", "KLNMA", "KLRHO", "KLSYN",
    "KLYPV", "KONKA", "KONTR", "KRDMA", "KRGYO", "KRPLS", "KRVGD", "KSTUR", "KTLEV", "KTSKR",
    "KZBGY", "KZGYO", "LILAK", "LINK", "LMKDC", "LUKSK", "LXGYO", "LYDHO", "LYDIA", "LYDYE",
    "MAALT", "MACKO", "MAKIM", "MAKTK", "MANAS", "MARBL", "MARKA", "MARMR", "MCARD", "MEGMT",
    "MEKAG", "MERIT", "MERKO", "METRO", "MEYSU", "MHRGY", "MMCAS", "MOPAS", "MRSHL", "MSGYO",
    "MTRYO", "MZHLD", "NETCD", "NPTLR", "OBASE", "ODINE", "ONRYT", "OPTGY", "OPTLR", "ORCAY",
    "ORMA", "OYLUM", "OYYAT", "OZATD", "OZGYO", "OZKGY", "OZRDN", "OZYSR", "PAGYO", "PAHOL",
    "PAMEL", "PASEU", "PATEK", "PCILT", "PEKGY", "PETUN", "PNLSN", "PNSUT", "POLTK", "PRDGS",
    "PRZMA", "PSDTC", "PSGYO", "QNBFK", "QNBTR", "RALYH", "RGYAS", "RNPOL", "RODRG", "ROYAL",
    "RUZYE", "RYSAS", "SAFKR", "SANEL", "SAYAS", "SDTTR", "SEGMN", "SEGYO", "SEKFK", "SEKUR",
    "SELVA", "SERNT", "SEYKM", "SKTAS", "SKYLP", "SKYMD", "SMART", "SMRVA", "SNICA", "SNPAM",
    "SUNTK", "SURGY", "SVGYO", "TABGD", "TARKM", "TBORG", "TCKRC", "TEHOL", "TERA", "TEZOL",
    "TGSAS", "TNZTP", "TRALT", "TRENJ", "TRHOL", "TRMET", "TUREX", "UCAYM", "UFUK", "ULAS",
    "ULUFA", "USAK", "VAKFA", "VANGD", "VBTYZ", "VERTU", "VERUS", "VKFYO", "VRGYO", "VSNMD",
    "YAPRK", "YAYLA", "YESIL", "YIGIT", "YONGA", "YYAPI", "YYLGD", "ZELOT", "ZERGY", "ZGYO",
]

_ALL_EXTRA = [
    # Ek BIST hisseleri
    "ACSEL", "ADEL", "ADESE", "AFYON", "AGROT", "AHGAZ", "AKBTU",
    "AKFYE", "AKCNS", "AKTIF", "AKTYP", "ALCAR", "ALFAS", "ALGYO",
    "ANGEN", "ANIM", "ANHYT", "ANELE", "APEKS", "ARAT", "ARDYZ",
    "ARENA", "ARSAN", "AVOD", "AVPGY", "AYCES", "AYGAZ", "AZTEK",
    "BANVT", "BARMA", "BASCM", "BFREN", "BIMAS", "BIZIM", "BMEKS",
    "BORLS", "BORSK", "BRKO", "BRKVY", "BRMEN", "BSOKE",
    "BTCIM", "BUCIM", "BURCE", "BURVA", "BVSAN",
    "CEOEM", "CLEBI", "CRFSA", "CUSAN",
    "DAGI", "DARDL", "DENGE", "DERIM", "DESA", "DESPC", "DGKLB",
    "DGNMO", "DITAS", "DMRGD", "DNISI", "DOBUR", "DOCO", "DOGUB",
    "DOKTA", "DURDO", "DYOBY",
    "EBEBK", "EGCYO", "EGGUB", "EGPRO", "EGSER", "EMKEL", "EMNIS",
    "ENKAI", "ENSRI", "ERSU", "ESCAR", "ESCOM", "ESEN",
    "ETILR", "ETYAT", "EUHOL",
    "FADE", "FENER", "FLAP", "FONET", "FORMT", "FORTE",
    "FRIGO", "FZLGY",
    "GARFA", "GENTS", "GESAN", "GIPTA", "GLBMD", "GLCVY",
    "GLRYH", "GLYHO", "GMTAS", "GOODY", "GRNYO", "GRSEL",
    "GSDDE", "GSDHO", "GSRAY", "GUNDG", "GZNMI",
    "HDFGS", "HEDEF", "HTTBT", "HUBVC", "HUNER",
    "HURGZ", "HZNDR",
    "IDEAS", "IDGYO", "IEYHO", "IHEVA", "IHGZT", "IHLAS",
    "IHLGM", "IHYAY", "IMASM", "INTEM", "IPEKE", "ISATR",
    "ISBIR", "ISDMR", "ISFIN", "ISYAT", "ITTFK", "IZFAS",
    "IZMDC", "IZOCM",
    "JOYS",
    "KARTN", "KFEIN", "KGYO", "KIPA", "KLKIM", "KLSER",
    "KMPUR", "KNFRT", "KOBI", "KOCMT", "KONYA", "KOPOL",
    "KOTON", "KRDMB", "KRONT", "KRSTL", "KRTEK",
    "KUTPO", "KVKK",
    "LIDER", "LIDFA", "LKMNH", "LNKNH",
    "MAGEN", "MARTI", "MEDTR", "MEGAP", "MEPET",
    "MGROS", "MINCO", "MNDRS", "MNDTR", "MOBTL", "MOGAN",
    "MPACT", "MPARK", "MRGYO", "MTRKS",
    "NATEN", "NETAS", "NIBAS", "NTGAZ", "NUGYO",
    "OBAMS", "ODAS", "OFMSN", "OKCMD", "OLMKS",
    "ORTDK", "OTKAR", "OTTO", "OYAYO",
    "PENGD", "PGSUS", "PINSU", "PKART", "PLTUR",
    "PRKME", "PRTAS",
    "QUAGR",
    "RTALB", "RUBNS",
    "SAMAT", "SANFM", "SARKY", "SERVE", "SMRTG",
    "SODSN", "SOKE", "SONME", "SRVGY", "SUWEN",
    "TATEN", "TATGD", "TCELL", "TDGYO", "TEKTU",
    "TKNSA", "TLMAN", "TMPOL", "TOASO", "TRCAS",
    "TRILC", "TSGYO", "TSGNL", "TUCLK", "TUKAS",
    "TUNSB", "TUPRS", "TURGG", "TURPW", "TUYAP",
    "UCAK", "ULUSE", "UMPAS", "UNLU", "URBNM",
    "UZEL",
    "VAKKO", "VBTS", "VESBE", "VESTL", "VKING",
    "WINTA",
    "YBTAS", "YGGYO", "YGYO", "YKSLN", "YLGYO",
    "YUNSA",
    "ZEDUR", "ZNGDK",
    "A1CAP", "A1YEN", "ASGYO",
]

BIST100 = list(dict.fromkeys(BIST30 + _BIST100_EXTRA))
ALL_STOCKS = list(dict.fromkeys(BIST100 + _ALL_EXTRA + _ALL_EXTRA_2))

CATEGORIES = {
    "BIST30": BIST30,
    "BIST100": BIST100,
    "TÜMÜ": ALL_STOCKS,
}
