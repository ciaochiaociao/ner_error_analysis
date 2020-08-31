import copy


def bioes2iob1(ner, last):
    
    def startwith(ner, prefix):
        return ner[0] == prefix

    def change_pre(ner, prefix):
        return prefix + ner[1:]

    def isend(ner):
        return startwith(ner, 'E') or startwith(ner, 'S')

    def isstart(ner):
        return startwith(ner, 'B') or startwith(ner, 'S')

    def isoutside(ner):
        return startwith(ner, 'O')

    def issametype(ner1, ner2):
        return ner1[2:] == ner2[2:]
    
    if isend(last) and isstart(ner) and issametype(last, ner):  # Boundary
        newner = change_pre(ner, 'B')
    elif not isoutside(ner):
        newner = change_pre(ner, 'I')
    else:
        newner = ner
    return newner


def bioes2iob1_list(ners):
    last = 'O'
    newners = []
    for ner in ners:
        newner = bioes2iob1(ner, last)
        last = ner
        newners.append(newner)
    return newners


def bioes2iob1_file(infile, outfile, bieos_cols=[1,2]):
    """
    Washington I-PER I-NNP
    ...
    
    bieos_cols: ex- [1,2]
    >>> bioes2iob1_file('test/wnut.test.gold.pred', 'test/wnut.test.gold.pred.iob1test')
    """
    if isinstance(infile, str):
        infile = open(infile, encoding='utf-8')
    if isinstance(outfile, str):
        outfile = open(outfile, 'w', encoding='utf-8')

    # add encoding='utf-8' to support windows OS
    lastcols = ['O'] * (max(bieos_cols) + 1)
    for line in infile:
        if line.strip():

            cols = line.split()
            newcols = copy.copy(cols)
            for bieos_col in bieos_cols:
                newcols[bieos_col] = bioes2iob1(cols[bieos_col], lastcols[bieos_col])

            lastcols = cols
            outfile.write(' '.join(newcols) + '\n')
        else:
            outfile.write(line)
            lastcols = ['O'] * (max(bieos_cols) + 1)
    infile.close()
    outfile.close()


def bioes2iob2(tag):
    return tag.replace('S-', 'B-').replace('E-', 'I-')


def bioes2iob2_file(infile, outfile, bieos_cols=[1,2]):

    if isinstance(infile, str):
        infile = open(infile, encoding='utf-8')
    if isinstance(outfile, str):
        outfile = open(outfile, 'w', encoding='utf-8')

    # add encoding='utf-8' to support windows OS
    for line in infile:
        if line.strip():
            cols = line.split()
            newcols = copy.copy(cols)
            for bieos_col in bieos_cols:
                newcols[bieos_col] = bioes2iob2(cols[bieos_col])

            outfile.write(' '.join(newcols) + '\n')
        else:
            outfile.write(line)
    infile.close()
    outfile.close()


def iob12iob2(tags):
    """
    Check that tags have a valid IOB format.
    Tags in IOB1 format are converted to IOB2.
    .. seealso:: `https://github.com/flairNLP/flair/blob/master/flair/data.py <https://github.com/flairNLP/flair/blob/master/flair/data.py>`_.
    """
    for i, tag in enumerate(tags):
        if tag == "O":
            new_tags.append(tag)
            continue

        # validity check (the case which is so invalid that it can not be fixed)
        split = tag.split("-")
        if len(split) != 2 or split[0] not in ["I", "B"]:
            # (cwhsu) check 'X-X' and 'B-, I-' # FIXME: len(split) == 3 when using wnut, e.g., I-creative-work
            return False
        if split[0] == "B":
            continue
        elif i == 0 or tags[i - 1] == "O":  # conversion IOB1 to IOB2
            # (cwhsu) case: 'I-X'; when the left boundary is detected (BOE, beginning of an entity)
            new_tags.append("B" + tag[1:])
        elif tags[i - 1][1:] == tag[1:]:
            # (cwhsu) case: 'I-X' and is not BOE; check if the suffix of the previous tag is the same as the current tag
            new_tags.append(tag)
            continue
        else:  # conversion IOB1 to IOB2
            # (cwhsu) case: 'I-X' + not BOE BUT has type mismatch with the previous tag of the same entity
            # => create a new entity
            # e.g. B-ORG I-PER => B-ORG B-PER
            new_tags.append("B" + tag[1:])

    return new_tags


def iob22iobes(tags):
    """
    IOB -> IOBES
    .. seealso:: modified from `https://github.com/flairNLP/flair/blob/master/flair/data.py <https://github.com/flairNLP/flair/blob/master/flair/data.py>`_.
    """
    new_tags = []
    for i, tag in enumerate(tags):
        if tag == "O":
            new_tags.append(tag)
        elif tag.split("-")[0] == "B":
            if i + 1 != len(tags) and tags[i + 1].split("-")[0] == "I":
                # (cwhsu) not reaching the right boundary (not EOE, not End Of an Entity)
                # note -        EOE:    EOS     OR      the next tag is not 'I' ('B-X' or 'O')
                #           not EOE: not EOS    AND     the next tag is     'I' ('B-X' or 'O')
                new_tags.append(tag)
            else:
                # (cwhsu) convert 'B' to 'S' when it's EOE
                new_tags.append(tag.replace("B-", "S-"))
        elif tag.split("-")[0] == "I":
            if i + 1 < len(tags) and tags[i + 1].split("-")[0] == "I":
                new_tags.append(tag)
            else:  # (cwhsu) convert 'I' to 'E' when it's EOE
                new_tags.append(tag.replace("I-", "E-"))
        else:
            raise Exception("Invalid IOB format!")
    return new_tags


def iob12iobes(tags):
    return iob22iobes(iob12iob2(tags))


if __name__ == '__main__':
    import argparse
    argparser = argparse.ArgumentParser()
    argparser.add_argument('-s', '--source', type=str)
    argparser.add_argument('--source-file', type=argparse.FileType('r'), default='-')
    argparser.add_argument('-t', '--target', type=str)
    argparser.add_argument('--target-file', type=argparse.FileType('w'), default='-')
    argparser.add_argument('--cols', nargs='*', default=[1, 2], type=int)
    args = argparser.parse_args()
    if args.source == 'bioes' and args.target == 'iob1':
        bioes2iob1_file(args.source_file, args.target_file, bieos_cols=args.cols)
    elif args.source == 'bioes' and args.target == 'iob2':
        bioes2iob2_file(args.source_file, args.target_file, args.cols)
    else:
        raise argparse.ArgumentError