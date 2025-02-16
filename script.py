import csv
from urllib.parse import quote
import unicodedata
import re
from pathlib import Path
import base64
import os
from os.path import exists
import json
import random
import requests

from bs4 import BeautifulSoup

ANKI_MEDIA = ".local/share/Anki2/User 1/collection.media/"


class Word:
    def __init__(self, csv_row):
        self.word = csv_row[2].strip()
        self.pos = csv_row[0].strip()
        self.cefr = csv_row[3].strip()
        self.frequency = csv_row[4].strip()
        self.note = csv_row[1].strip()
        self.vocalization = None
        self.transliteration = None
        self.definitions = None

    def fetch_translit(self):
        if not self.transliteration:
            translit = get_translit(self.word)
            self.transliteration = translit["transliteration"]
            self.vocalization = translit["vowels"]

    def fields(self):
        self.fetch_all()
        definitions = self.definitions[:3]
        fields = [
            self.word,
            self.vocalization,
            self.transliteration,
            self.frequency,
        ]
        for (index, definition) in enumerate(definitions):
            def_fields = [
                definition.headword,
                definition.pos,
                definition.example,
                definition.example_vocalization,
                definition.example_transliteration,
                definition.cloze(index + 1),
                definition.example_trans,
            ]
            fields += def_fields
        fields += [""] * 6 * (3 - len(definitions))
        fields.append(self.cefr)
        fields = [csv_escape(item) if item is not None else "" for item in fields]
        return fields

    def fetch_definitions(self):
        if not self.definitions:
            self.definitions = reverso_defs(self.word)

    def fetch_all(self):
        self.fetch_translit()
        self.fetch_definitions()
        [example.fetch_translit() for example in self.definitions]

    def download_audio(self):
        anki_path = Path.home() / Path(ANKI_MEDIA)
        self.fetch_all()
        pairs = [(self.word, self.transliteration)] + [
            (definition.example_text(), definition.example_transliteration)
            for definition in self.definitions
        ]
        for (arabic, transliteration) in pairs:
            filename = anki_path / Path(translit_to_audio_filename(transliteration))
            if exists(filename):
                print(f"Found file {filename}")
                continue
            url = get_audio_url(arabic)
            bitrate = "20k"
            command = f'ffmpeg -i "{url}" -b:a {bitrate} "{filename}"'
            print(command)

    def poll_vowels(self):
        """Compare the vocalizations returned by the Reverso API for the
        headword and example sentences, both as they are and with final
        diacritics removed.

        The Reverso API that returns vocalizations and transliterations from
        Arabic text is more reliable with longer texts, as it has more context
        for each word. This function looks at the various vocalizations and
        carries out a vote, whereby the headword's vocalization has one vote and
        the (presumably) more reliable example sentence vocalizations have two.
        The options are compared both as they are and with final diacritics
        removed. If not all the options agree, the one with the fewest votes is
        removed and another vote carried out. This continues until all options
        match or until only one option remains, at which point it becomes the
        headword's vocalization.
        """
        self.fetch_all()
        example_vowels = [self.vocalization]
        for definition in self.definitions:
            if definition.example is None or definition.example == "":
                continue
            def_word = get_sel(definition.example)
            if def_word == self.word:
                example_vowels.append(get_sel(definition.example_vocalization))
        candidates = []
        for (vowels, index) in zip(example_vowels, list(range(4))):
            votes = 1 if index == 0 else 2
            try:
                index = [cand[0] for cand in candidates].index(vowels)
            except Exception:
                candidates.append([vowels, votes, index])
            else:
                candidates[index][1] += votes
        if len(candidates) == 1:
            # print(self.vocalization)
            return False
        candidates.sort(key=lambda n: [n[1], n[0]])
        result = candidates[0][0]
        index = candidates[0][2]
        rounds = len(candidates) - 1
        for round in range(rounds):
            # print(candidates)
            final_removed = [
                [remove_final_diacritic(word[0]), word[2]] for word in candidates
            ]
            if (
                all_equal([word[0] for word in final_removed])
                or len(final_removed) == 2
            ):
                result = final_removed[-1][0]
                index = final_removed[-1][1]
                break
            candidates = candidates[1:]
        self.vocalization = result
        if index > 0:
            self.transliteration = get_sel(
                self.definitions[index - 1].example_transliteration
            )
        # print(self.vocalization)
        return True


class Definition:
    def __init__(self, headword, pos, example, example_trans):
        self.headword = headword
        self.pos = pos
        self.example = example
        self.example_trans = example_trans
        self.example_transliteration = None
        self.example_vocalization = None

    def example_text(self):
        if not self.example:
            return None
        return BeautifulSoup(self.example, "lxml").text

    def fetch_translit(self):
        if self.example and not self.example_transliteration:
            translit = get_translit(self.example)
            self.example_transliteration = translit["transliteration"]
            self.example_vocalization = translit["vowels"]

    def word_vowels(self):
        if not self.example:
            return None
        html = BeautifulSoup(self.example_vocalization, "lxml")
        word = html.find(class_="sel").text
        return word

    def word_transliteration(self):
        if not self.example:
            return None
        html = BeautifulSoup(self.example_transliteration, "lxml")
        word = html.find(class_="sel").text
        return word

    def cloze(self, number):
        if not self.example:
            return None
        word = get_sel(self.example)
        reg = re.compile('<span class="sel">.*</span>')
        return re.sub(reg, f"{{{{c{number}::{word}}}}}", self.example)


def get_sel(html):
    html = BeautifulSoup(html, "lxml")
    return html.find(class_="sel").text


def get_translit(text):
    payload = {
        "text": text,
        "model": "ar-wikipedia",
    }
    r = requests.get(
        "https://lang-utils-api.reverso.net/transliteration", params=payload
    )
    return json.loads(r.text)


def get_words(path):
    words = []
    with open(path, "r") as file:
        reader = csv.reader(file, delimiter=",")
        for row in reader:
            words.append(Word(row))
    return words[1:]


def write_words(words, csv_path, count):
    already_written = []
    number = 0
    with open(csv_path, "r") as file:
        reader = csv.reader(file, delimiter=",")
        for row in reader:
            already_written.append(row[0])
            number = int(row[4])
    with open(csv_path, "a") as file:
        for index in range(count):
            if index == len(words):
                break
            if words[index].word in already_written:
                print(f"Already written {words[index].word}")
            else:
                words[index].fetch_all()
                words[index].poll_vowels()
                if words[index].definitions != []:
                    fields = words[index].fields()
                    number += 1
                    string = ",".join(
                        fields[:4] + [csv_escape(str(number))] + fields[4:]
                    )
                    file.write(string + "\n")


def random_word(words):
    return random.choice(words)


def random_test(count):
    words = get_words("arabic_words.csv")
    random_words = []
    for _ in range(count):
        random_words.append(random_word(words))
    return random_words


def get_page(url):
    headers = {
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:10.0) Gecko/20100101 Firefox/10.0"
    }
    html = requests.get(url, headers=headers).text
    return BeautifulSoup(html, "lxml")


def get_audio_url(text):
    return requests.post(
        "https://ttsmp3.com/makemp3_new.php",
        data={"msg": text, "lang": "Zeina", "source": "ttsmp3"},
    ).json()["URL"]


def firefox(url):
    os.system(f"firefox {url}")


def reverso_url(word):
    return f"https://dictionary.reverso.net/arabic-english/{quote(word)}/forced"


def wiktionary_url(word):
    return f"https://en.wiktionary.org/wiki/{quote(word)}"


def inner_html(html):
    if html is None:
        return None
    return "".join([str(item) for item in html.contents])


def reverso_defs(word):
    print(f"Looking up {word}")
    url = reverso_url(word)
    page = get_page(url)
    defs = []
    trans_boxes = page.find_all(id="transBox")
    for box in trans_boxes:
        # Some words have a "More translations and examples" box of colspan 2,
        # which we don't want.
        if box.get("colspan", None):
            continue
        # Others have an "Other examples in context" box of class "notrans"
        if box.find(class_="notrans"):
            continue
        name = box.find(id="translationName")
        headword = name.text
        pos = box.find(class_="redCateg").text
        next_row = name.find_next("tr")
        if next_row:
            example = inner_html(next_row.find(class_="src"))
            example_trans = inner_html(next_row.find(class_="tgt"))
        else:
            example = None
            example_trans = None
        defs.append(Definition(headword, pos, example, example_trans))
    return defs


def ar_to_audio_filename(text):
    """Return a filename containing a base 64 encoding of text.

    This method of constructing filenames has the advantage that the text can be
    unambiguously reconstructed. The downside is that the filenames are long and
    not human-readable.
    """
    base64_str = base64.urlsafe_b64encode(bytes(text, "utf-8")).decode("ascii")
    return f"ar_{base64_str}.mp3"


def audio_filename_to_ar(filename):
    reg = re.compile(r"ar_(.*)\.mp3")
    base64_str = reg.search(filename).group(1)
    return base64.urlsafe_b64decode(bytes(base64_str, "ascii")).decode("utf-8")


def translit_to_audio_filename(translit):
    """Return a filename with only ASCII characters, based on an ALA-C
    romanization.

    This method produces human-readable filenames. The downside is that it does
    not allow the unambiguous reconstruction of the original sentence in Arabic
    script.
    """
    ascii_text = translit_to_ascii(translit)
    words_in_filename = 7
    ascii_text = "-".join(ascii_text.split(" ")[:words_in_filename])
    reg = re.compile(r"[^\d\w-]")
    ascii_text = reg.sub("", ascii_text)
    sanitized = (
        unicodedata.normalize("NFKD", ascii_text)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    return f"ar_{sanitized}.mp3"


def translit_to_ascii(translit):
    """Accept an Arabic transliteration of the sort provided by the Reverso
    transliteration API (generally corresponding to ALA-C
    https://www.loc.gov/catdir/cpso/romanization/arabic.pdf) and return it with
    each non-ASCII character replaced by one or two ASCII characters. 
    
    This system is inspired by the Arabic chat alphabet
    (https://en.wikipedia.org/wiki/Arabic_chat_alphabet).
    """
    replacements = [
        ("ā", "aa"),
        ("ī", "ii"),
        ("ū", "uu"),
        ("ʾ", "2"),
        ("ʿ", "3"),
        ("ḍ", "D"),
        ("ḡ", "gh"),
        ("ḥ", "H"),
        ("ṣ", "S"),
        ("ṭ", "T"),
        ("ṯ", "th"),
        ("ẓ", "DH"),
    ]
    for replacement in replacements:
        translit = translit.replace(replacement[0], replacement[1])
    return translit


def test_def():
    words = get_words("arabic_words.csv")
    word = random_word(words)
    firefox(reverso_url(word.word))
    defs = word.definitions()
    # firefox(get_audio_url(word.definitions()[0].example_text()))
    for definition in defs:
        print(f"{definition.headword} {definition.pos}")
        print(definition.example_text())
        # if definition.example_text():
        # translit = get_translit(definition.example_text())
        # print(translit["vowels"])
        # print(translit_to_audio_filename(translit["transliteration"]))
        # print(translit["transliteration"])
        print(definition.example_trans)
        print("\n")
    return word


def bitrate_test(text):
    url = get_audio_url(text)
    bitrates = list(range(8, 36, 4))
    for bitrate in bitrates:
        command = f'ffmpeg -i "{url}" -b:a {bitrate}k "test{bitrate}.mp3"'
        os.system(command)
    # for some reason, 16k and 20k result in the same file size.
    # I'll go with 20k, although the difference is negligible.


def max_defs(sample):
    random_words = random_test(sample)
    return max([len(word.definitions()) for word in random_words])


def csv_escape(string):
    string = string.replace('"', '""')
    return f'"{string}"'


def fix_csv():
    wrong = "tocorrect.csv"
    fixed = "corrected.csv"
    rows = []
    offset = 19
    with open(wrong, "r") as file:
        reader = csv.reader(file, delimiter=",")
        for row in reader:
            rows.append(row)
    rows = [row[:4] + [str(int(row[4]) + offset)] + row[5:] for row in rows]
    with open(fixed, "a") as file:
        for row in rows:
            row = [csv_escape(item) for item in row]
            row_string = ",".join(row)
            file.write(row_string + "\n")


def read_words(csv_path):
    words = []
    with open(csv_path, "r") as file:
        reader = csv.reader(file, delimiter=",")
        for row in reader:
            word = Word([""] * 5)
            word.word = row[0]
            word.vocalization = row[1]
            word.transliteration = row[2]
            word.frequency = row[3]
            word.definitions = []
            def_starts = list(range(5, len(row), 7))[:3]
            for start in def_starts:
                if row[start] != "":
                    items = [row[index + start] for index in [0, 1, 2, 6]]
                    definition = Definition(*items)
                    definition.example_vocalization = row[start + 3]
                    definition.example_transliteration = row[start + 4]
                    word.definitions.append(definition)
            words.append(word)
    return words


def is_arabic_diacritic(char):
    # https://www.unicode.org/charts/PDF/U0600.pdf
    reg = re.compile(r"[\u064b-\u065f]")
    return reg.search(char)


def remove_final_diacritic(word):
    if is_arabic_diacritic(word[-1]):
        return word[:-1]
    return word


def all_equal(items):
    for item in items[1:]:
        if item != items[0]:
            return False
    return True


def main():
    words = get_words("arabic_words.csv")
    write_words(words, "to_import.csv", len(words))
