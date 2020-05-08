import argparse
import itertools

from doc2vec.data import batch_dm, batch_dbow, doc
from doc2vec.model import dm, dbow, model
from doc2vec import vocab


MODEL_TYPES = {
    'dm': (dm.DM, batch_dm.data_generator, batch_dm.batch),
    'dbow': (dbow.DBOW, batch_dbow.data_generator, batch_dbow.batch)
}


def _parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument('path', help='Path to documents directory')

    parser.add_argument('--model', default='dm',
                        choices=list(MODEL_TYPES.keys()),
                        help='Which model to use')
                        
    parser.add_argument('--save', help='Path to save model')
    parser.add_argument('--save_period', 
                        type=int,
                        help='Save model every n epochs')
    parser.add_argument('--save_vocab', help='Path to save vocab file')
    parser.add_argument('--save_doc_embeddings',
                        help='Path to save doc embeddings file')
    parser.add_argument('--save_doc_embeddings_period',
                        type=int,
                        help='Save doc embeddings every n epochs')

    parser.add_argument('--load', help='Path to load model')
    parser.add_argument('--load_vocab', help='Path to load vocab file')

    parser.add_argument('--early_stopping_patience',
                        type=int,
                        help='Stop after no loss decrease for n epochs')

    parser.add_argument('--vocab_size', default=vocab.DEFAULT_SIZE,
                        type=int,
                        help='Max vocabulary size; ignored if loading from file')
    parser.add_argument('--vocab_rare_threshold',
                        default=vocab.DEFAULT_RARE_THRESHOLD,
                        type=int,
                        help=('Words less frequent than this threshold '
                              'will be considered unknown'))

    parser.add_argument('--window_size',
                        default=model.DEFAULT_WINDOW_SIZE,
                        type=int,
                        help='Context window size')
    parser.add_argument('--embedding_size',
                        default=model.DEFAULT_EMBEDDING_SIZE,
                        type=int,
                        help='Word and document embedding size')

    parser.add_argument('--num_epochs',
                        default=model.DEFAULT_NUM_EPOCHS,
                        type=int,
                        help='Number of epochs to train for')
    parser.add_argument('--steps_per_epoch',
                        default=model.DEFAULT_STEPS_PER_EPOCH,
                        type=int,
                        help='Number of samples per epoch')

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--train', dest='train', action='store_true')
    #group.add_argument('--no-train', dest='train', action='store_false')
    group.set_defaults(train=False)

    group.add_argument('--test', dest='test', action='store_true')
    #group.add_argument('--no-test', dest='test', action='store_false')
    group.set_defaults(test=False)

    return parser.parse_args()


def main():
    args = _parse_args()

    tokens_by_doc_id = doc.tokens_by_doc_id(args.path)

    num_docs = len(tokens_by_doc_id)

    v = vocab.Vocabulary()
    if args.load_vocab:
        v.load(args.load_vocab)
    else:
        all_tokens = list(itertools.chain.from_iterable(tokens_by_doc_id.values()))
        v.build(all_tokens, max_size=args.vocab_size)
        if args.save_vocab:
            v.save(args.save_vocab)

    token_ids_by_doc_id = {d: v.to_ids(t) for d, t in tokens_by_doc_id.items()}

    model_class, data_generator, batcher = MODEL_TYPES[args.model]

    m = model_class(args.window_size, v.size, num_docs,
                    embedding_size=args.embedding_size)

    if args.load:
        m.load(args.load)
    else:
        m.build()
        m.compile()

    #elapsed_epochs = 0

    if args.train:
        all_data = batcher(
                data_generator(
                    token_ids_by_doc_id,
                    args.window_size,
                    v.size))

        history = m.train(
                all_data,
                epochs=args.num_epochs,
                steps_per_epoch=args.steps_per_epoch,
                early_stopping_patience=args.early_stopping_patience,
                save_path=args.save,
                save_period=args.save_period,
                save_doc_embeddings_path=args.save_doc_embeddings,
                save_doc_embeddings_period=args.save_doc_embeddings_period)

        elapsed_epochs = len(history.history['loss'])

        if args.save:
            m.save(args.save.format(epoch=elapsed_epochs))

        if args.save_doc_embeddings:
            m.save_doc_embeddings(args.save_doc_embeddings.format(epoch=elapsed_epochs))

    elif args.test:

        m_test = model_class(args.window_size, v.size, num_docs,
                             embedding_size=args.embedding_size)

        m_test.build()

        layer_ids=[]
        if(args.model=='dbow'):
            layer_ids = [2, 3, 4]
        else:
            layer_ids = [3, 4, 5, 6, 7, 8]

        for layer_id in layer_ids:
          m_test.replace_weights(layer_id, m.get_weights(layer_id))
          m_test.freeze_layer(layer_id)

        m_test.compile()

        all_data = batcher(
            data_generator(
                token_ids_by_doc_id,
                args.window_size,
                v.size))

        history = m_test.train(
             all_data,
             epochs=args.num_epochs,
             steps_per_epoch=args.steps_per_epoch,
             early_stopping_patience=args.early_stopping_patience,
             save_path=args.save,
             save_period=args.save_period,
             save_doc_embeddings_path=args.save_doc_embeddings,
             save_doc_embeddings_period=args.save_doc_embeddings_period)

        elapsed_epochs = len(history.history['loss'])


        if args.save:
           m_test.save(args.save.format(epoch=elapsed_epochs))

        if args.save_doc_embeddings:
           m_test.save_doc_embeddings(args.save_doc_embeddings.format(epoch=elapsed_epochs))
