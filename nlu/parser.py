from nlu.data import *
from nlu.parser_utils import *


class ConllParser(Base):  #TODO: create methods that returns ConllDocuments
    """Column Parser for CoNLL03 formatted text file"""
    TAGGERSOURCE = 'gold'

    def __init__(self, filepath: str, cols_format: List[Dict[str, Union[str, int]]] = None, tag_scheme='iob1') -> None:
        """
            :param filepath: The filename. Note that the file loaded should end with two blank lines!!!
            :param cols_format:
                - type: predict | gold
                - col_num: starts from 0
                - tagger: ner | pos | chunk
        >>> import os.path
        >>> cols_format = [{'type': 'predict', 'col_num': 1, 'tagger': 'ner'}, {'type': 'gold', 'col_num': 2, 'tagger': 'ner'}]
        >>> path = os.path.dirname(os.path.abspath(__file__)) + '/../test/train.pred.gold'
        >>> train_parser = ConllParser(path, cols_format)
        >>> train_parser  # doctest: +ELLIPSIS
        ConllParser(filepath='.../test/train.pred.gold', cols_format=[{'type': 'predict', 'col_num': 1, 'tagger': 'ner'}, {'type': 'gold', 'col_num': 2, 'tagger': 'ner'}])
        >>> train_parser.obtain_statistics(entity_stat=True, source='predict')  # doctest: +ELLIPSIS
        ---...
        Document number:  946
        Sentence number:  14041
        Token number:  203621
        PER: 6599 (28%)
        LOC: 7134 (30%)
        ORG: 6324 (27%)
        MISC: 3435 (15%)
        TOTAL: 23492
        >>> train_parser.set_entity_mentions()
        """
        newfilepath = filepath + '.iob1'
        self.tag_scheme = tag_scheme
        if tag_scheme in ['iob1', 'bio1']:
            newfilepath = filepath
        elif tag_scheme in ['iob2', 'bio2']:
            bioes2iob1_file(filepath, newfilepath, bieos_cols=[col['col_num'] for col in cols_format if col['tagger'] == 'ner'])
        elif tag_scheme in ['ioblu', 'iobes']:
            bioes2iob1_file(filepath, newfilepath, bieos_cols=[col['col_num'] for col in cols_format if col['tagger'] == 'ner'])
        else:
            raise ValueError('Invalid tagging scheme')
        
        filepath = newfilepath
        
        # attributes
        self.docs = []
        self.filepath = filepath
        if cols_format is None:
            self.cols_format = [{'type': 'predict', 'col_num': 1, 'tagger': 'ner'},
                                {'type': 'gold', 'col_num': 2, 'tagger': 'ner'}]
        else:
            self.cols_format = cols_format

        self.doc_sep_tok = doc_sep_tok

        tok_dicts = ConllParser.parse_conll_to_tok_dicts(self.filepath, self.cols_format, self.doc_sep_tok)
        self.docs = ConllParser.build_md_docs_from_tok_dicts(tok_dicts)

        self.tag_policy = tag_policy
        self.ann_states = set()

        # optional back reference functionality: token1.sentence, sentence5.document
        ConllParser.add_back_refs_for_md_docs(self.docs)

    @property
    def doc_sep_line(self):
        _num_o = len(self.docs[0][0][0].line.split()) - 1
        return ' '.join(['-DOCSTART-'] + ['O'] * _num_o) + '\n'

    def __repr__(self):
        entity_stat = True if 'entity_ann' in self.ann_states else False
        print('(Parser Annotations)', *self.ann_states)
        self.obtain_statistics(entity_stat=entity_stat, debug=True, tag_policy=self.tag_policy)
        if 'error_ann' in self.ann_states:
            self.error_overall_stats()
        return ''

    @staticmethod
    def parse_conll_to_tok_dicts(filepath: str, cols_format, doc_sep_tok='-DOCSTART-') -> List[List[List[dict]]]:
        """read a conll-formatted text file to a hierarchical collection of token dictionaries (tok_dict is like below)
        input:
        filepath - the file path of the conll-formatted file
        cols_format - [{'type': 'predict', 'col_num': 1, 'tagger': 'ner'},
                        {'type': 'gold', 'col_num': 2, 'tagger': 'ner'},
                        {'type': 'predict', 'col_num': 3, 'tagger': 'pos'},
                        ...
                        {'type': 'predict', col_num': 7, 'tagger': 'ner_conf'}
                        ...]
        output: 
        same as the input of function build_md_docs_from_tok_dicts() where
        tok_dict = {
            'text': 'Obama',
            'poss': {'predict': 'NN', 'gold': 'NN'},
            'chunks': {'predict': 'I-NNP', 'gold': 'I-NNP'},
            'ners': {'predict': 'I-PER', 'gold': 'I-PER'},
            'ner_conf': {'predict': 0.9993}
            }
        """
        
        # parse cols_format
        len_pos = len([col for col in cols_format if col['tagger'] == 'pos'])
        len_chunk = len([col for col in cols_format if col['tagger'] == 'chunk'])
        len_ner = len([col for col in cols_format if col['tagger'] == 'ner'])
        try:
            col_conf = [col['col_num'] for col in cols_format if col['tagger'] == 'ner_conf'][0]
        except IndexError:
            col_conf = None
        total_cols = len(cols_format) + 1  # text with annotations
        
        # set doc_sep_tok
        # doc_sep_tok = ' '.join(['-DOCSTART-'] + ['-X-'] * len_pos + ['O'] * len_chunk + ['O'] * len_ner + \
        #                 ['O'] * (1 if col_conf else 0)) + '\n'  # TODO: consider the order given by cols_format
        print('doc_sep_tok:', doc_sep_tok)
        
        docs, sentences, tokens = [], [], []
        with open(filepath, encoding='utf-8') as f:

            # parse conll formatted txt file to ConllParser class
            for ix, line in tqdm(enumerate(f), desc='LINE'):
                if line.startswith(doc_sep_tok):  # -DOCSTART-|: end of a document
                    if sentences:  # if not empty document
                        docs.append(sentences)
                        sentences = []
                elif not line.strip():  # blank line: the end of a sentence
                    if tokens:  # if not empty sentence (like after -DOCSTART-)
                        sentences.append(tokens)
                        tokens = []
                else:  # inside a sentence: every token
                    a = line.strip().rsplit(' ', maxsplit=total_cols-1)
                    poss = {col['type']: ConllPosTag(a[col['col_num']])
                            for col in cols_format if col['tagger'] == 'pos'} if len_pos else None
                    chunks = {col['type']: ConllChunkTag(a[col['col_num']])
                              for col in cols_format if col['tagger'] == 'chunk'} if len_chunk else None
                    ners = {col['type']: ConllNERTag(a[col['col_num']])
                            for col in cols_format if col['tagger'] == 'ner'} if len_ner else None
                    ner_conf = a[col_conf] if col_conf is not None else None
                    tokens.append({'text': a[0], 'poss': poss, 'chunks': chunks, 'ners': ners, 'ner_conf': ner_conf,
                                   'line': line, 'line_no': ix})
            if sentences:  # for the last document (without -DOCSTART- at the end)
                docs.append(sentences)
        if len(docs) > 0:
            return docs
        elif len(docs) == 0 and len(sentences) > 0:
            return [sentences]
        else:
            return [[tokens]]

    
    @staticmethod
    def add_back_refs_for_md_docs(docs: List[Document]) -> None:  # TODO: Maybe it can be moved to sentence or other places?
        for doc in docs:
            for sent in doc:
                sent.set_document(doc)
                for tok in sent:
                    tok.set_sentence(sent)
                try:
                    for em in sent.entity_mentions_dict.values():
                        em.set_sentence(sent)
                except AttributeError:
                    pass  # to remove

    @staticmethod
    def build_md_docs_from_tok_dicts(docs: List[List[List[dict]]]) -> List[Document]:  
        # TODO: Maybe it can further be abstracted such that it can be put in other classes than ConllParser?
        """build the multi-document class from token dictionarys, which are like
        input:
        docs -  [
                    [  # first doc
                        [ tok_dict1, tok_dict2, ...], # first sent
                        [...],
                        ...
                    ], 
                    [...],
                    ...
                ]
                where
                tok_dict = {
                    'text': 'Obama',
                    'poss': {'predict': 'NN', 'gold': 'NN'},
                    'chunks': {'predict': 'I-NNP', 'gold': 'I-NNP'},
                    'ners': {'predict': 'I-PER', 'gold': 'I-PER'},
                    'ner_conf': 0.99983
                    }
        """
            
        did, sid, tid = -1, -1, -1

        docs_classes = []

        for doc in tqdm(docs, desc='DOC'):
            did += 1
            sid = -1
            sents_classes = []
            for sent in doc:
                sid += 1
                tid = -1
                toks_classes = []
                for tok in sent:
                    tid += 1
                    toks_classes.append(ConllParser.build_conll_token_from_tok_dicts(tok, tid, sid, did))
                sents_classes.append(Sentence(toks_classes))
            docs_classes.append(Document(sents_classes))
        
        return docs_classes
    
    
    
    @staticmethod
    def build_conll_token_from_tok_dicts(tok, tid, sid, did) -> ConllToken:
        """build a ConllToken from token dictionarys, which are like
        tok_dict = {
        'text': 'Obama',
        'poss': {'predict': 'NN', 'gold': 'NN'},
        'chunks': {'predict': 'I-NNP', 'gold': 'I-NNP'},
        'ners': {'predict': 'I-PER', 'gold': 'I-PER'},
        'ner_conf': 0.99983
        }
        """
        return ConllToken(tok['text'], poss=tok['poss'], chunks=tok['chunks'], ners=tok['ners'], conf=tok['ner_conf'],
                          line=tok['line'], line_no=tok['line_no'],
                          id_=tid, sid=sid, did=did)
            
    def set_entity_mentions(self, tag_policy=None) -> None:
        """chunk entity mentions for all sources (i.e. predict, gold)
        effect: call sentence.set_entity_mentions function for all sentences in the parser.docs
        """
        for doc in self.docs:
            for sentence in doc.sentences:
                sentence.set_entity_mentions([src['type'] for src in self.cols_format])

        if tag_policy is None:
            tag_policy = self.tag_policy
        # set different types of entity mentions from different sources
        if tag_policy == 'conll':
            _types = ['PER', 'LOC', 'ORG', 'MISC']
        elif tag_policy == 'wnut':
            _types = ['person', 'location', 'corporation', 'creative-work', 'group', 'product']
        else:
            raise ValueError('illegal tag_policy {} (should be conll, wnut or ...)'.format(tag_policy))
            
        for source in [src['type'] for src in self.cols_format]:
            preffix = 'pred' if source == 'predict' else 'gold'
            ems_attr_name = preffix[0] + 'ems'  # 'pems'/'gems'
            attr_names = [preffix + '_' + _type.lower() + 's' for _type in _types]  # self.pred_pers/self.gold_miscs/...
            
            for attr_name in attr_names:
                self.__setattr__(attr_name, [])
            for doc in self.docs:
                for sentence in doc.sentences:
                    try:
                        for entity_mention in sentence.entity_mentions_dict[source]:
                            attr_name = preffix + '_' + entity_mention.type.lower() + 's'
                            self.__getattribute__(attr_name).append(entity_mention)  # set self.pred_pers/self.gold_miscs/...
                    except KeyError:
                        pass
            
            self.__setattr__(ems_attr_name, [])
            for attr_name in attr_names:
                self.__setattr__(ems_attr_name, self.__getattribute__(ems_attr_name) + self.__getattribute__(attr_name))  # set self.gems/self.pems
        self.tag_policy = tag_policy
        self.ann_states.add('entity_ann')

    @staticmethod
    def set_errors(parser, gold_src, predict_src):  # FIXME: deprecated. set_errors_xx() duplicated method with methods in NERErrorAnnotator
        for doc in parser.docs:
            ConllParser.set_errors_in_document(doc, gold_src, predict_src)

    @staticmethod
    def set_errors_in_document(doc, gold_src, predict_src):  # FIXME: deprecated
        for sentence in doc.sentences:
            ConllParser.set_errors_in_sentence(sentence, gold_src, predict_src)

    @staticmethod
    def set_errors_in_sentence(sentence: Sentence, gold_src, predict_src) -> None:  # FIXME: deprecated
        """
        effect: set sentence.ems_pairs, sentence.ner_results, sentence.corrects, sentence.errors
        """
        sentence.ems_pairs: Union['EntityMentionsPairs', None] = ConllParser.get_pairs(sentence, gold_src, predict_src)  # FIXME: No get_pairs method any more. 
        sentence.ner_results: List[Union['NERErrorComposite', 'NERCorrect']] = None if sentence.ems_pairs is None else \
            sentence.ems_pairs.results

        sentence.set_corrects_from_pairs(sentence.ems_pairs)
        sentence.set_errors_from_pairs(sentence.ems_pairs)

        for ems_pair in sentence.ems_pairs:
            try:
                for pem in ems_pair.pems:
                    for tok in pem.tokens:
                        tok.ems_pair = ems_pair
            except TypeError:
                pass
            try:
                for gem in ems_pair.gems:
                    for tok in gem.tokens:
                        tok.ems_pair = ems_pair
            except TypeError:
                pass

        # TODO: unify the setter or property usage

    def obtain_statistics(self, entity_stat=False, source=None, debug=False, tag_policy='conll') -> None:

        print(f'---{self.filepath} ({source})---')
        print('Document number: ', len([doc for doc in self.docs]))
        print('Sentence number: ', len([sen for doc in self.docs for sen in doc.sentences]))
        print('Token number: ', len([token for doc in self.docs for sen in doc.sentences for token in sen.tokens]))

        if source is None:
            source = self.TAGGERSOURCE

        if entity_stat:
            if tag_policy == 'conll':
                _types = ['PER', 'LOC', 'ORG', 'MISC']
            elif tag_policy == 'wnut':
                _types = ['person', 'location', 'corporation', 'creative-work', 'group', 'product']
            else:
                raise ValueError('illegal tag_policy {} (should be conll, wnut or ...)'.format(tag_policy))
            ent_tot = len(self.__getattribute__(source[0] + 'ems'))
            for type_ in _types:
                ems = self.__getattribute__(source[:4] + '_' + type_.lower() + 's')
                print(type_ + ': {} ({:.0%})'.format(len(ems), len(ems)/ent_tot))
            print('TOTAL: {}'.format(ent_tot))

        if debug:
            print('--- debugging info ---')
            _d = {
                'Empty document number': len([doc for doc in self.docs if not doc]),
                'Empty sentence number': len([sen for doc in self.docs for sen in doc.sentences if not sen]),
                'Empty token number': len([token for doc in self.docs
                                               for sen in doc.sentences
                                               for token in sen.tokens if not token]),
                'Empty-content token number': len([token for doc in self.docs for sen in doc.sentences
                                                       for token in sen.tokens if not len(token.text)]),
                'Empty-id token number': len([token for doc in self.docs for sen in doc.sentences
                                                  for token in sen.tokens if token.id is None]),
                'Token id error number': [(sen.tokens[-1].id, len(sen.tokens)-1) for doc in self.docs
                                               for sen in doc.sentences if sen.tokens[-1].id != len(sen.tokens)-1],
                'Fullid of empty sentences':[sen.fullid for doc in self.docs
                                                  for sen in doc.sentences if not sen]
            }

            for _s, _v in _d.items():
                if _v:
                    print(f'{_s}: {_v}')

    def error_overall_stats(self) -> None:  # TODO: move to NERErrorAnalyzer

        # count all errors
        correct_total = 0
        error_total = 0
        ol_total = 0
        sen_total = 0
        for doc in self.docs:
            for sentence in doc:
                sen_total += 1
                if sentence.ems_pairs:
                    ol_total += 1
                    for corr in sentence.ner_corrects:
                        if corr:
                            correct_total += 1

                    for error in sentence.ner_errors:
                        if error:
                            error_total += 1
        print('---Overall Results---')
        print('found entity mentions:', len(self.pems))
        print('true entity mentions:', len(self.gems))
        print('correct_total: ', correct_total)
        print('error_total: ', error_total)
        self.precision = correct_total/len(self.pems)
        self.recall = correct_total/len(self.gems)
        self.microf1 = 2 * self.precision * self.recall / (self.recall + self.precision)
        print('precision: {:.2%}'.format(self.precision))
        print('recall: {:.2%}'.format(self.recall))
        print('micro-f1: {:.2%}'.format(self.microf1))
        print('corrects ratio: {:.2%}'.format(correct_total/(correct_total+error_total)))
        print('all corrects and errors', correct_total + error_total)
        print('the number of sentences with/without entities (predict + gold): {} ({:.0%}), {} ({:.0%})'.format(
            ol_total, ol_total/sen_total, sen_total - ol_total, (sen_total - ol_total)/sen_total))

    def print_all_errors(self) -> None:
        for doc in self.docs:
            for sentence in doc:
                if sentence.ner_errors:
                    for error in sentence.ner_errors:
                        print(str(error))

    def print_n_errors(self, n=50) -> None:
        import random

        errors = []

        for doc in self.docs:
            for sentence in doc:
                if sentence.ner_errors:
                    for error in sentence.ner_errors:
                        errors.append(str(error))

        randomized = random.sample(errors, n)

        for error in randomized:
            print(error)

    def print_corrects(self, num=10):
        count = 0
        for doc in self.docs:
            for sentence in doc:
                count += 1
                if count % num == 0:
                    sentence.print_corrects()

    def print_n_corrects(self, n=50):

        import random
        correct_sents = []

        for doc in self.docs:
            for sentence in doc:
                correct_sents.append(sentence)

        randomized = random.sample(correct_sents, n)

        for correct_sent in randomized:
            correct_sent.print_corrects()

    def save_result(self, fname='result.tsv'):
        with open(fname, 'w', encoding='utf-8') as f:
            f.write('id\tresult_type\tpem_word\tpem_type\tgem_word\tgem_type\tsentence\n')
            for doc in self.docs:
                for sent in doc:
                    for ner_result in sent.ner_results:
                        f.write(ner_result.sep_str() + '\n')
                        
    def get_from_fullid(self, fullid):
        """
        :param fullid: ex - 'D0-S3-T2'
        :return: object, ex - Token
        >>> parser.get_from_fullid('D0-S3-T2').fullid
        'D0-S3-T2'
        """
        attr_name_table = {
            'D': 'docs',
            'S': None,
            'T': None,
            'GEM': 'gems',
            'PEM': 'pems',
            'PAIR': 'ems_pairs'
        }

        abs_id_table = {
            'NERErr': 'ner_errors',
            'NERCorr': 'ner_corrects'
        }

        import re

        ids = fullid.split('-')

        obj = self
        for id in ids:
            prefix, idx = list(filter(None, re.split('(\D+)', id)))
            idx = int(idx)
            if prefix in attr_name_table:
                table = attr_name_table
            elif prefix in abs_id_table:  # found absolute id => set obj back to the ancestor `parser`
                table = abs_id_table
                obj = self
            else:
                raise KeyError('prefix {} is not valid'.format(prefix))

            attr_name = table[prefix]

            if attr_name is not None:
                obj = obj.__getattribute__(attr_name)[idx]
            else:  # use  __getitem__
                obj = obj[idx]

        return obj

    def next(self, obj, step=1):
        return self.move_to(obj, step)

    def prev(self, obj, step=1):
        return self.move_to(obj, -step)
    
    def move_to(self, obj, step=1):
        self_pre, self_id = list(obj.self_ids.items())[-1]
        new_ids = OrderedDict()
        new_ids.update(obj.parent_ids)
        new_ids.update({self_pre: self_id + step})
        new_ids = MD_IDs(new_ids)

        try:
            return self.get_from_fullid(new_ids.fullid)
        except ValueError:  # id turns to '-N' which resembles another prefix w/o id
            raise IndexError('Reach the beginning of a collection')
        except IndexError:
            raise IndexError('Reach the end of a collection')


class EntityMentionAnnotator:
    # put set_entity_mentions() here
    pass


if __name__ == '__main__':

    import os.path
    import doctest

    failure_count, test_count = doctest.testmod()
#     doctest.run_docstring_examples(ConllParser.get_entity_mentions_from_sent, globals())
    if failure_count == 0:
        
        print('{} tests passed!!!!!!'.format(test_count))
    
        path = os.path.dirname(os.path.abspath(__file__)) + '/../test/train.pred.gold'
        train_parser = ConllParser(path)
        train_parser.obtain_statistics(entity_stat=True, source='predict')
        train_parser.set_entity_mentions()
