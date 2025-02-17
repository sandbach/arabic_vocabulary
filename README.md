# Arabic vocabulary Anki deck

This repository contains an [Anki](https://ankiweb.net/) deck for Arabic vocabulary and a script with functions used to create it.

## How it's made

### Vocabulary

The words in the deck are taken from the [Kelly project](https://spraakbanken.gu.se/projekt/kelly)'s Arabic frequency list, which I found through Wiktionary's [list of Arabic frequency lists](https://en.wiktionary.org/wiki/Wiktionary:Frequency_lists/Arabic). The file [arabic_words.csv](arabic_words.csv) contains the Kelly project data. A list of words sorted by frequency is essential for this sort of deck, as it allows learners to tackle the most common words first.

### Definitions

Definitions and example sentences for the words in the list come from [Reverso](https://www.reverso.net/text-translation), which is a truly great resource. 

The function `reverso_defs` in the Python script takes a word and scrapes the Reverso page for up to three definitions, each of which may have an example sentence in Arabic and a translation of that sentence. These example sentences appear all together on the 'Arabic word' Anki card for a word and individually on the 'Arabic cloze' cards. Helpfully, the examples and translations on Reverso have the target word marked up as `<span class="sel">`, so it's easy to make the important word in the sentence stand out on the Anki card.

### Vocalization and transliteration

In Arabic, short vowels are generally not written. There are only three short vowels in Arabic, so native readers can usually deduce the appropriate vowel from context. This is not terribly useful for learners, however. Writing for children and foreign learners (and in the Qur'an, where accurate recitation is essential) employs a system of [diacritics](https://en.wikipedia.org/wiki/Arabic_diacritics#harakat) to mark short vowels. The Kelly project list does not include these diacritics, so I needed a way to find the vocalization for arbitrary Arabic words and sentences.

Reverso has an API that takes an Arabic word and returns a vocalization and transliteration for it. This is great, but it comes with some problems:

1. Vocalizations for individual words are unreliable.
2. Vocalizations correspond to a very conservative version of Modern Standard Arabic and indicate some aspects of pronunciation that are not generally used by MSA speakers today, and are never used in Arabic dialects (especially [tanwīn تَنْوِين](https://en.wikipedia.org/wiki/Arabic_diacritics#Tanw%C4%ABn)).

Problem 1 derives from the fact that one sequence of Arabic letters without vowel diacritics can correspond to multiple words, or multiple inflections of the same word, all with different short vowels. Compare the four different words at [كتب – Wiktionary](https://en.wiktionary.org/wiki/%D9%83%D8%AA%D8%A8); without knowing the context, even a native Arabic speaker could only guess at which vocalization would be suitable. When the Reverso API receives a single Arabic word, it also has to guess.

My assumption is that when given a longer text, the Reverso API returns more reliable results for each word in the text. The script uses this as the basis for the `poll_vowels` method, which compares the vocalizations for the headword on its own and in each of the example sentences and goes through rounds of 'voting', whereby the headword vocalization has one vote and the example sentence vocalizations each have two votes. If all the vocalizations match, there is no change. If not, they are compared with their final diacritic removed and the one with the fewest votes removed until a single vocalization remains.

For example, given the sequence درب, the candidates are as follows: دَرُبٌّ has one vote, دَرْبٍ has two, and دَرْبِ has four. They do not match with their final diacritics removed, so the candidate with the fewest votes is eliminated. The remaining candidates match with final diacritics removed, so the vocalization is corrected to دَرْب. 

This system is of course not guaranteed to produce correct results, but it provides a partial solution to problems 1 and 2 without much effort.

## Notes on importing

The Anki notes have the following fields:

- Word
- Vowels
- Transliteration
- Frequency
- Number
- Def1
- PoS1
- Example1
- Vowels1
- Transliteration1
- Cloze1
- English1
- Def2
- PoS2
- Example2
- Vowels2
- Transliteration2
- Cloze2
- English2
- Def3
- PoS3
- Example3
- Vowels3
- Transliteration3
- Cloze3
- English3
- Tags

There are two note types, 'Arabic word' and 'Arabic cloze'. Each word is numbered, so that its 'word' and 'cloze' cards end up next to each other. This means that each new card is immediately followed by its first cloze card. If you want to avoid this, you could create a new version of [to_import.csv](to_import.csv) where the cards are in the same order but the numbering is offset by ten, for example.

Working with Arabic (and right-to-left text in general) in text editors can cause problems. I recommend the font [Readex Pro](https://github.com/ThomasJockin/readexpro), which is highly legible and looks good alongside a fixed-width Latin font. Emacs is capable of handling bidirectional text correctly.

## Further possibilities

As it stands, the deck uses text-to-speech for Arabic audio. You might want to use a different TTS engine to the one included on your device, and store MP3 files as part of the deck. See the [Anki Manual](https://docs.ankiweb.net/importing/text-files.html#importing-media) for details on how to do this. The Python script contains some sample functions for creating audio filenames based on Arabic text that include only ASCII characters: one that uses base 64 encoding and one that produces an ASCII version of a transliteration.
