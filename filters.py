class Adequacy():
  
  def __init__(self, model_tag='prithivida/parrot_adequacy_on_BART'):
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    self.nli_model = AutoModelForSequenceClassification.from_pretrained(model_tag)
    self.tokenizer = AutoTokenizer.from_pretrained(model_tag)

  def filter(self, input_phrase, para_phrases, adequacy_threshold, device="cpu"):
      top_adequacy_phrases = []
      for para_phrase in para_phrases:
        x = self.tokenizer.encode(input_phrase, para_phrase, return_tensors='pt',truncation_strategy='only_first')
        self.nli_model = self.nli_model.to(device)
        logits = self.nli_model(x.to(device))[0]
        # we throw away "neutral" (dim 1) and take the probability of "entailment" (2) as the adequacy score
        entail_contradiction_logits = logits[:,[0,2]]
        probs = entail_contradiction_logits.softmax(dim=1)
        prob_label_is_true = probs[:,1]
        adequacy_score = prob_label_is_true[0].item()
        if adequacy_score >= adequacy_threshold:
            top_adequacy_phrases.append(para_phrase)
      return top_adequacy_phrases


  def score(self, input_phrase, para_phrases, adequacy_threshold, device="cpu"):
      adequacy_scores = {}
      for para_phrase in para_phrases:
        x = self.tokenizer.encode(input_phrase, para_phrase, return_tensors='pt',truncation_strategy='only_first')
        self.nli_model = self.nli_model.to(device)
        logits = self.nli_model(x.to(device))[0]
        # we throw away "neutral" (dim 1) and take the probability of "entailment" (2) as the adequacy score
        entail_contradiction_logits = logits[:,[0,2]]
        probs = entail_contradiction_logits.softmax(dim=1)
        prob_label_is_true = probs[:,1]
        adequacy_score = prob_label_is_true[0].item()
        if adequacy_score >= adequacy_threshold:
          adequacy_scores[para_phrase] = adequacy_score
      return adequacy_scores

class Fluency():
  def __init__(self, model_tag='prithivida/parrot_fluency_on_BERT'):
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    self.cola_model = AutoModelForSequenceClassification.from_pretrained(model_tag, num_labels=2)
    self.cola_tokenizer = AutoTokenizer.from_pretrained(model_tag)

  def filter(self, para_phrases, fluency_threshold, device="cpu"):
      import numpy as np
      from scipy.special import softmax
      self.cola_model = self.cola_model.to(device)
      top_fluent_phrases = []
      for para_phrase in para_phrases:
        input_ids = self.cola_tokenizer("Sentence: " + para_phrase, return_tensors='pt', truncation=True)
        input_ids = input_ids.to(device)
        prediction = self.cola_model(**input_ids)
        scores = prediction[0][0].detach().cpu().numpy()
        scores = softmax(scores)
        fluency_score = scores[1] # LABEL_0 = Bad Fluency, LABEL_1 = Good Fluency
        if fluency_score >= fluency_threshold:
          top_fluent_phrases.append(para_phrase)
      return top_fluent_phrases

  def score(self, para_phrases, fluency_threshold, device="cpu"):
      import numpy as np
      from scipy.special import softmax
      self.cola_model = self.cola_model.to(device)
      fluency_scores = {}
      for para_phrase in para_phrases:
        input_ids = self.cola_tokenizer("Sentence: " + para_phrase, return_tensors='pt', truncation=True)
        input_ids = input_ids.to(device)
        prediction = self.cola_model(**input_ids)
        scores = prediction[0][0].detach().cpu().numpy()
        scores = softmax(scores)
        fluency_score = scores[1] # LABEL_0 = Bad Fluency, LABEL_1 = Good Fluency
        if fluency_score >= fluency_threshold:
          fluency_scores[para_phrase] = fluency_score
      return fluency_scores
      


class Diversity():

  def __init__(self, model_tag='paraphrase-distilroberta-base-v2'):
    from sentence_transformers import SentenceTransformer
    self.diversity_model = SentenceTransformer(model_tag)

  def rank(self, input_phrase, para_phrases, diversity_ranker='levenshtein'):
      if diversity_ranker == "levenshtein":
        return self.levenshtein_ranker(input_phrase, para_phrases)
      elif diversity_ranker == "euclidean":
        return self.euclidean_ranker(input_phrase, para_phrases)
      elif diversity_ranker == "diff":
        return self.diff_ranker(input_phrase, para_phrases)

  def euclidean_ranker(self, input_phrase, para_phrases):
      import pandas as pd
      from sklearn_pandas import DataFrameMapper
      from sklearn.preprocessing import MinMaxScaler
      from scipy import spatial

      diversity_scores = {}
      outputs = []
      input_enc = self.diversity_model.encode(input_phrase.lower())
      for para_phrase in para_phrases:              
          paraphrase_enc = self.diversity_model.encode(para_phrase.lower())
          euclidean_distance = (spatial.distance.euclidean(input_enc, paraphrase_enc))
          outputs.append((para_phrase,  euclidean_distance))
      df = pd.DataFrame(outputs, columns=['paraphrase', 'scores'])
      fields = []
      for col in df.columns:
          if col == "scores":
              tup = ([col], MinMaxScaler())
          else:  
              tup = ([col], None)
          fields.append(tup) 

      mapper = DataFrameMapper(fields, df_out=True)
      for index, row in mapper.fit_transform(df.copy()).iterrows():
          diversity_scores[row['paraphrase']] = row['scores']
      return  diversity_scores

  def levenshtein_ranker(self, input_phrase, para_phrases):
      import Levenshtein
      diversity_scores = {}
      for para_phrase in para_phrases:              
          distance = Levenshtein.distance(input_phrase.lower(), para_phrase)
          diversity_scores[para_phrase] =  distance
      return diversity_scores
  
  def diff_ranker(self, input_phrase, para_phrases):
    import difflib
    differ = difflib.Differ()
    diversity_scores ={}
    for para_phrase in para_phrases:
        diff = differ.compare(input_phrase.split(), para_phrase.split())
        count = 0
        for d in diff:
          if "+" in d or "-" in d:
            count += 1
        diversity_scores[para_phrase] = count
    return diversity_scores
