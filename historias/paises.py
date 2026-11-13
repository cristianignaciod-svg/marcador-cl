"""Selecciones: nombre (español / inglés / variantes de ESPN y FotMob) -> código de bandera.
Se compara por nombre exacto (sin tildes ni signos), nunca por parecido: "Irlanda" no es "Irlanda del Norte"."""
import re
import unicodedata

PAISES = {
    # UEFA
    "al": ["Albania"], "ad": ["Andorra"], "am": ["Armenia"], "at": ["Austria"], "az": ["Azerbaiyán", "Azerbaijan"],
    "by": ["Bielorrusia", "Belarus"], "be": ["Bélgica", "Belgium"],
    "ba": ["Bosnia y Herzegovina", "Bosnia-Herzegovina", "Bosnia and Herzegovina", "Bosnia & Herzegovina", "Bosnia"],
    "bg": ["Bulgaria"], "hr": ["Croacia", "Croatia"], "cy": ["Chipre", "Cyprus"],
    "cz": ["República Checa", "Rep. Checa", "Chequia", "Czechia", "Czech Republic"],
    "dk": ["Dinamarca", "Denmark"], "gb-eng": ["Inglaterra", "England"], "ee": ["Estonia"],
    "fo": ["Islas Feroe", "Feroe", "Faroe Islands", "Faroe Is."], "fi": ["Finlandia", "Finland"],
    "fr": ["Francia", "France"], "ge": ["Georgia"], "de": ["Alemania", "Germany"], "gi": ["Gibraltar"],
    "gr": ["Grecia", "Greece"], "hu": ["Hungría", "Hungary"], "is": ["Islandia", "Iceland"],
    "ie": ["Irlanda", "República de Irlanda", "Rep. de Irlanda", "Republic of Ireland", "Ireland"],
    "il": ["Israel"], "it": ["Italia", "Italy"], "kz": ["Kazajistán", "Kazajstán", "Kazakhstan"],
    "xk": ["Kosovo"], "lv": ["Letonia", "Latvia"], "li": ["Liechtenstein"], "lt": ["Lituania", "Lithuania"],
    "lu": ["Luxemburgo", "Luxembourg"], "mt": ["Malta"], "md": ["Moldavia", "Moldova"], "me": ["Montenegro"],
    "nl": ["Países Bajos", "Holanda", "Netherlands"], "mk": ["Macedonia del Norte", "North Macedonia", "Macedonia"],
    "gb-nir": ["Irlanda del Norte", "Northern Ireland"], "no": ["Noruega", "Norway"], "pl": ["Polonia", "Poland"],
    "pt": ["Portugal"], "ro": ["Rumania", "Rumanía", "Romania"], "ru": ["Rusia", "Russia"],
    "sm": ["San Marino"], "gb-sct": ["Escocia", "Scotland"], "rs": ["Serbia"], "sk": ["Eslovaquia", "Slovakia"],
    "si": ["Eslovenia", "Slovenia"], "es": ["España", "Spain"], "se": ["Suecia", "Sweden"],
    "ch": ["Suiza", "Switzerland"], "tr": ["Turquía", "Türkiye", "Turkey"], "ua": ["Ucrania", "Ukraine"],
    "gb-wls": ["Gales", "Wales"],
    # CONMEBOL
    "ar": ["Argentina"], "bo": ["Bolivia"], "br": ["Brasil", "Brazil"], "cl": ["Chile"], "co": ["Colombia"],
    "ec": ["Ecuador"], "py": ["Paraguay"], "pe": ["Perú", "Peru"], "uy": ["Uruguay"], "ve": ["Venezuela"],
    # CONCACAF
    "mx": ["México", "Mexico"], "us": ["Estados Unidos", "EE.UU.", "EEUU", "USA", "United States"],
    "ca": ["Canadá", "Canada"], "cr": ["Costa Rica"], "pa": ["Panamá", "Panama"], "hn": ["Honduras"],
    "jm": ["Jamaica"], "sv": ["El Salvador"], "gt": ["Guatemala"], "ht": ["Haití", "Haiti"],
    "tt": ["Trinidad y Tobago", "Trinidad and Tobago"], "cw": ["Curazao", "Curaçao", "Curacao"],
    "ni": ["Nicaragua"], "cu": ["Cuba"], "do": ["República Dominicana", "Rep. Dominicana", "Dominican Republic"],
    # AFC
    "jp": ["Japón", "Japan"], "kr": ["Corea del Sur", "South Korea", "Korea Republic", "Corea"],
    "au": ["Australia"], "ir": ["Irán", "Iran", "IR Iran"], "sa": ["Arabia Saudita", "Arabia Saudí", "Saudi Arabia"],
    "qa": ["Catar", "Qatar"], "ae": ["Emiratos Árabes Unidos", "Emiratos Árabes", "United Arab Emirates", "UAE"],
    "iq": ["Irak", "Iraq"], "jo": ["Jordania", "Jordan"], "uz": ["Uzbekistán", "Uzbekistan"],
    "cn": ["China", "China PR"], "om": ["Omán", "Oman"], "bh": ["Baréin", "Bahrein", "Bahrain"],
    "kp": ["Corea del Norte", "North Korea"], "in": ["India"], "id": ["Indonesia"], "th": ["Tailandia", "Thailand"],
    "vn": ["Vietnam"], "sy": ["Siria", "Syria"], "ps": ["Palestina", "Palestine"],
    "nz": ["Nueva Zelanda", "New Zealand"],
    # CAF
    "ma": ["Marruecos", "Morocco"], "sn": ["Senegal"], "tn": ["Túnez", "Tunisia"], "dz": ["Argelia", "Algeria"],
    "eg": ["Egipto", "Egypt"], "ng": ["Nigeria"], "gh": ["Ghana"], "cm": ["Camerún", "Cameroon"],
    "ci": ["Costa de Marfil", "Ivory Coast", "Côte d'Ivoire", "Cote d'Ivoire"], "ml": ["Malí", "Mali"],
    "za": ["Sudáfrica", "South Africa"], "cv": ["Cabo Verde", "Cape Verde"],
    "cd": ["RD Congo", "R.D. del Congo", "DR Congo", "Congo DR", "República Democrática del Congo"],
    "bf": ["Burkina Faso"], "gn": ["Guinea"], "ga": ["Gabón", "Gabon"], "ao": ["Angola"],
    "zm": ["Zambia"], "ug": ["Uganda"], "bj": ["Benín", "Benin"], "ke": ["Kenia", "Kenya"],
}


def clave(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


_INDICE = {clave(n): iso for iso, ns in PAISES.items() for n in ns}
CONMEBOL = {"ar", "bo", "br", "cl", "co", "ec", "py", "pe", "uy", "ve"}


def iso_de(nombre):
    """Código de la selección o None. Ignora sufijos tipo 'Sub-21' (esos no son la selección mayor)."""
    k = clave(nombre)
    if re.search(r"\b(sub|u) ?\d\d\b|\bfem|women", k):
        return None
    return _INDICE.get(k)
