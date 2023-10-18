import logging

import cologne_phonetics
import Levenshtein

def compare_words_phonetic(s1, s2) -> float:
    #print(f'\n\n>>>> CMP {s1} {s2}')

    s1_phonetics = cologne_phonetics.encode(s1)
    s2_phonetics = cologne_phonetics.encode(s2)

    #print(f'{s1} -> {s1_phonetics}')
    #print(f'{s2} -> {s2_phonetics}')
    #print('\n')

    best_ratio = 0

    for w1 in s1_phonetics:
        for w2 in s2_phonetics:
            r12 = Levenshtein.ratio(w1[1], w2[1])
            #print(f'PHON {w1}/{w2} = {r12}')
            best_ratio = max(best_ratio, r12)

    return best_ratio


class Contact:
    def __init__(self, name: str, number: str, aliases: list[str]):
        self.name = name
        self.number = number
        self.aliases = aliases

    def is_strict_match(self, s: str):
        """ Is self a strict match with the provided string"""
        s = s.lower()
        if self.name.lower() == s:
            return True
        for alias in self.aliases:
            if alias.lower() == s:
                return True
        return False

    def similarity_score(self, s: str) -> float:
        """ Returns an arbitrary similarity score
        from s to this contact
        """

        s = s.lower()

        if self.is_strict_match(s):
            #print(f'{s}/{self} STRICT')
            return 1

        score = 0
        # Is s part of the contact ?
        for n in [self.name] + self.aliases:
            #print(f'Will do {s}')
            # Speech in name: "Max" in "Max Power"
            if s in n.lower():
                #print(f'{s}/{n}: s in n')
                score = max(score, 0.7)
            # Speech in name: "Max" in "I wanna call Max"
            if n.lower() in s:
                #print(f'{s}/{n}: n in s')
                score = max(score, 0.7)

            phonetic_score = compare_words_phonetic(s, n)
            #print(f'PHONITIC {s}/{n} = {phonetic_score}')
            score = max(score, phonetic_score)

        return score

    def __repr__(self):
        return f'<Contact {self.name} ({self.aliases}) → {self.number}>'


contacts = [
    Contact('Bob Lawrance', '+41791234567', ['Bob']),
    Contact('Alice', '+41761234566', ['Mirabelly']),
    Contact('Heinz', '+41799999999', ['Valser', 'Heinz Valser']),
]

def get_matching_contacts(s: str, min_score = .5) -> list[Contact]:
    """ Returns a sorted list of contacts, from the most
    likely to the less one"""

    similar_contacts = {}
    for contact in contacts:
        c_score = contact.similarity_score(s)
        print(f'{s}/{contact} = {c_score}')
        if c_score > min_score:
            similar_contacts[contact] = c_score


    print(similar_contacts)
    l = sorted(similar_contacts.keys(), key=lambda c: -similar_contacts[c])

    logging.debug(f'MACHING CONTACTS OF {s} is {l}')
    return l
