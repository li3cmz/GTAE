import json 
import pdb
from tqdm import tqdm
import numpy as np
import argparse
import math
import os
import tensorflow as tf
from classifier.clas_test_distr import generate_style_distr
from style_transfer_intensity import load_style_distributions
from style_transfer_intensity import calculate_direction_corrected_emd
from style_lexicon import load_lexicon
from utils import load_dataset
from utils import merge_datasets
from utils import MessageContainer
from content_preservation import mask_style_words
from content_preservation import generate_style_modified_texts
from content_preservation import load_word2vec_model
from content_preservation import calculate_wmd_scores
from naturalness import NeuralBasedClassifier

args = argparse.ArgumentParser(description='evaluating the model')
args.add_argument('--dataset', type=str, default='yelp', help='the dataset to use')
args.add_argument('--model', type=str, default='GTAE-alfa-20200702-0', help='the model to evaluate')
args.add_argument('--eval', type=str, default='all', help='style_transfer, or content_preservation, or naturalness')
args = args.parse_args()

dataset = args.dataset
model = args.model
eval_sti, eval_cp, eval_nat = False, False, False
if args.eval == 'all':
    eval_sti, eval_cp, eval_nat = True, True, True
elif args.eval == 'style_transfer': 
    eval_sti = True
elif args.eval == 'content_preservation':
    eval_cp = True
elif args.eval == 'naturalness':
    eval_nat = True
else:
    raise ValueError('--eval {} is not supported!'.format(args.eval))

msgs = MessageContainer()

msgs.append('========================================')
msgs.append('(1) Dataset: {} (2) Model: {}'.format(dataset, model))
msgs.append('========================================')
if eval_sti:
    tf.reset_default_graph()
    msgs.append('Evaluating Style Transfer Intensity')
    msgs.append('========================================')
    # Generate ori/trans_distribution.npz
    for style_ in ['trans', 'ori']:
        print('Generating {}_distribution.npz...'.format(style_))
        test_accu = generate_style_distr(dataset, model, style_)
        if style_ == 'trans': trans_accu = test_accu

    # Calculate direction-corrected EMD
    trans_distr, trans_labels = load_style_distributions('eval_results/{}/{}/trans_distribution.npz'.format(dataset, model))
    ori_distr, ori_labels = load_style_distributions('eval_results/{}/{}/ori_distribution.npz'.format(dataset, model))
    textcnn_itensities = []
    print('Calculating direction-corrected EMD scores...')
    for i in tqdm(range(len(trans_labels))):
        tmp_textcnn_itensity = calculate_direction_corrected_emd(ori_distr[i], trans_distr[i], trans_labels[i])
        textcnn_itensities.append(tmp_textcnn_itensity)
    mean_EMD = np.mean(textcnn_itensities)
    msgs.append('transfer accuracy: {}'.format(trans_accu))
    msgs.append('mean EMD: {}'.format(mean_EMD))
    msgs.append('========================================')

if eval_cp:
    tf.reset_default_graph()
    msgs.append('Evaluating Content Preservation')
    msgs.append('========================================')
    datatype = 'sentiment' if dataset == 'yelp' else dataset
    styles = {0: 'binary {}'.format(datatype)}
    style_features_and_weights_path = 'style_lexicon/style_words_and_weights_{}.json'.format(dataset)
    loaded_style_lexicon = load_lexicon(styles, style_features_and_weights_path)
    
    ori_texts = load_dataset('eval_results/{}/{}/ori.text'.format(dataset, model))
    trans_texts = load_dataset('eval_results/{}/{}/trans.text'.format(dataset, model))
    _, _, ori_texts_masked = generate_style_modified_texts(ori_texts, loaded_style_lexicon)
    _, _, trans_texts_masked = generate_style_modified_texts(trans_texts, loaded_style_lexicon)
    
    w2v_model_masked = load_word2vec_model('eval_models/word2vec_masked_{}'.format(dataset)) 
    
    wmd_scores_masked = calculate_wmd_scores(ori_texts_masked, trans_texts_masked, w2v_model_masked)
    all_wmd_scores_masked = 0
    num_wmd_scores_masked = 0
    for score_ in wmd_scores_masked:
        if not math.isinf(score_):
            all_wmd_scores_masked += score_
            num_wmd_scores_masked += 1
    mean_wmd_scores_masked = all_wmd_scores_masked / num_wmd_scores_masked
    msgs.append('mean masked WMD: {}'.format(mean_wmd_scores_masked))
    msgs.append('-> for bert-scores: e.g., python -u eval_bert.py --dataset yelp --model GTAE-alfa-20200702-0')
    msgs.append('========================================')
    
if eval_nat:
    tf.reset_default_graph()
    msgs.append('Evaluating Naturalness')
    msgs.append('========================================')
    trans_texts = load_dataset('eval_results/{}/{}/trans.text'.format(dataset, model))
    naturalness_results = dict()
    for naturalness_type in ['ARAE', 'CAAE', 'DAR']:
        neural_classifier = NeuralBasedClassifier(naturalness_type)
        scores = neural_classifier.score(trans_texts)
        mean_score = np.mean(scores)
        naturalness_results[naturalness_type] = mean_score
    
    for naturalness_type in ['ARAE', 'CAAE', 'DAR']:
        msgs.append('mean naturalness score from {} model: {}'.format(naturalness_type, naturalness_results[naturalness_type]))
        msgs.append('========================================')

msgs.display()
