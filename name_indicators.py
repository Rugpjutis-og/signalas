"""Original-language account-name clues. These are heuristics, not identity proof.

Keep scripts intact; do not translate names or transliterate ambiguous words.
Patterns are casefolded/accent-insensitive for matching only. Extend with tested
phrases, not place names, nationalities or political views.
"""
MULTILINGUAL_INDICATORS = {
    'media': [
        r'newsroom|newspaper|broadcast\w*|news\s+agency|daily\s+news',
        r'новост\w*|газет\w*|телеканал\w*|информационн\w*\s+агентств\w*',
        r'новин\w*|телебачення|інформаційн\w*\s+агентств\w*',
        r'wiadomosci|gazeta|telewizj\w*|agencj\w*\s+prasow\w*',
        r'zinas|laikrakst\w*|televizij\w*',
        r'nachrichten\w*|zeitung\w*|presseagentur\w*',
        r'agence\s+de\s+presse|journal|noticias|agencia\s+de\s+noticias',
    ],
    'business': [
        r'limited|gmbh|sarl|srl|plc|corporation|enterprises|business|shop|store',
        r'ооо|оао|зао|тов|компани\w*|предприяти\w*|магазин\w*|підприємств\w*|крамниц\w*',
        r'spolk\w*|przedsiebiorstw\w*|sklep\w*|sia|uznemum\w*|veikal\w*',
        r'entreprise\w*|societe|empresa\w*|tienda\w*|unternehmen|geschaft\w*',
    ],
    'institution': [
        r'ministry|municipality|city\s+council|government|embassy|police|armed\s+forces',
        r'министерств\w*|міністерств\w*|правительств\w*|уряд|посольств\w*|полици\w*|поліці\w*|администраци\w*|міськ\w*\s+рад\w*',
        r'ministerstw\w*|urzad|policj\w*|ambasad\w*|pasvaldib\w*|ministrij\w*|policij\w*',
        r'ministerium|stadtverwaltung|regierung|polizei|botschaft|ministere|mairie|gouvernement|ministerio|ayuntamiento|gobierno',
    ],
    'organization': [
        r'political\s+party|foundation|association|charity|nonprofit|non-profit|trade\s+union',
        r'партия|партії|партія|фонд\w*|ассоциаци\w*|асоціаці\w*|организаци\w*|організаці\w*|благотворительн\w*|благодійн\w*',
        r'parti\w*|fundacj\w*|stowarzyszeni\w*|biedrib\w*|nodibinajum\w*',
        r'stiftung\w*|verein|partei|fondation|association|fundacion|asociacion|partido',
    ],
    'education_health_community': [
        r'university|school|college|hospital|clinic|library|museum|community\s+cent(?:er|re)|church|parish',
        r'университет\w*|університет\w*|школ\w*|больниц\w*|лікарн\w*|клиник\w*|клінік\w*|библиотек\w*|бібліотек\w*|музе\w*|церков\w*|церкв\w*|приход|парафі\w*',
        r'uniwersytet\w*|szkol\w*|szpital\w*|bibliotek\w*|parafi\w*|universitat\w*|skola|slimnic\w*|draudz\w*',
        r'universite|ecole|hopital|bibliotheque|musee|universidad|escuela|hospital|iglesia|schule|krankenhaus|kirche',
    ],
}
