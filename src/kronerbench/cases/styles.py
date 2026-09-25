"""Named, reversible amount renderings. Whole markers require zero cents."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Style:
    group: str = ""
    decimal: str = ","
    prefix: str = ""
    suffix: str = ""
    sign: str = "leading"
    whole: str = ""
    currency: str = "NOK"

    def render(self, minor: int) -> str:
        units, cents = divmod(abs(minor), 100)
        if self.whole and cents:
            raise ValueError("Whole-unit markers require zero cents.")
        integer = f"{units:,}".replace(",", self.group)
        text = integer + (self.whole or f"{self.decimal}{cents:02}")
        if minor < 0:
            if self.sign == "parentheses":
                text = f"({text})"
            elif self.sign == "trailing":
                text += "-"
            else:
                text = self.sign.replace("leading", "-") + text
        return self.prefix + text + self.suffix


STYLES = {
    "canonical": Style(),
    "space-comma": Style(" "),
    "dot-comma": Style("."),
    "comma-dot": Style(",", "."),
    "plain-dot": Style("", "."),
    "apostrophe-dot": Style("'", ".", currency="CHF"),
    "curly-apostrophe": Style("’", ".", currency="CHF"),
    "nbsp": Style("\u00a0"),
    "narrow-nbsp": Style("\u202f"),
    "thin-space": Style("\u2009"),
    "figure-space": Style("\u2007"),
    "nok-prefix": Style(" ", prefix="NOK "),
    "nok-suffix": Style(" ", suffix=" NOK"),
    "kr-prefix": Style(" ", prefix="kr "),
    "kr-dot-suffix": Style(" ", suffix=" kr."),
    "euro-prefix": Style(".", prefix="€ ", currency="EUR"),
    "euro-suffix": Style("\u202f", suffix=" €", currency="EUR"),
    "irish-euro": Style(",", ".", prefix="€", currency="EUR"),
    "swiss-franc": Style("'", ".", prefix="CHF ", currency="CHF"),
    "swiss-fr": Style("'", ".", prefix="Fr. ", currency="CHF"),
    "pound": Style(",", ".", prefix="£", currency="GBP"),
    "czech": Style(" ", suffix=" Kč", currency="CZK"),
    "hungarian": Style(" ", suffix=" Ft", currency="HUF"),
    "polish": Style(" ", suffix=" zł", currency="PLN"),
    "swedish-colon": Style(" ", ":", currency="SEK"),
    "sek-suffix": Style(" ", suffix=" SEK", currency="SEK"),
    "dkk-prefix": Style(".", prefix="DKK ", currency="DKK"),
    "isk-suffix": Style(".", suffix=" ISK", currency="ISK"),
    "dash-zero": Style(" ", whole=",-"),
    "double-dash": Style(" ", whole=",--"),
    "en-dash-zero": Style(" ", whole=",–"),
    "swiss-whole": Style("'", whole=".–", currency="CHF"),
    "dot-dash": Style("", whole=".-"),
    "swedish-whole": Style(" ", whole=":-", currency="SEK"),
    "parentheses": Style(" ", sign="parentheses"),
    "sap-minus": Style(".", sign="trailing"),
    "unicode-minus": Style(" ", sign="−"),
    "en-dash-minus": Style(" ", sign="–"),
    "ungrouped-eur": Style("", prefix="EUR ", currency="EUR"),
    "apostrophe-comma": Style("'"),
}


def render(minor: int, name: str) -> str:
    return STYLES[name].render(minor)
