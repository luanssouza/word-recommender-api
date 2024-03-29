import numpy as np
import pandas as pd
import nltk
from nltk.corpus import wordnet as wn
import os

from src.connection import db_connection

def get_aspects(conn, mov_id):
    return pd.read_sql('SELECT aspect, score FROM ASPECT WHERE movie_id = %s' % mov_id, con=conn)

def get_title(conn, mov_prof, mov_rec):
    return pd.read_sql('SELECT movie_id, title FROM MOVIE WHERE movie_id in (%s, %s)' % (mov_prof, mov_rec), con=conn, index_col='movie_id')

def get_titles_movies(conn, mov_prof: list, mov_rec):
    ids = ",".join(str(i) for i in mov_prof)
    return pd.read_sql('SELECT movie_id, title FROM MOVIE WHERE movie_id in (%s, %s)' % (ids, mov_rec), con=conn, index_col='movie_id')

def get_movies(conn, user_id):
    stmt = 'SELECT movie_id FROM USERMOVIE WHERE user_id = {0}'.format(user_id)
    return pd.read_sql(stmt, con=conn)

# get n (number) aspects most important to the movie that
# has a meaning on wordnet
def get_n_aspects(number: int, aspects_movie: pd.DataFrame):
    n = 0
    output = []
    for index, row in aspects_movie.iterrows():
        if n >= number:
            break
        aspect = row["aspect"]
        if not aspect:
            continue
        syns = wn.synsets(aspect)
        if len(syns) > 0:
            output.append(syns[0])
            n = n + 1

    return output

def join_words(words: list):
    join_w = "\", \"".join(words[:-1])
    join_w = "\" and \"".join([join_w, words[-1]])
    return join_w

def generate_explanations(profile_itens: list, top_item: int):
    # nltk.download('wordnet')
    
    nltk.data.path.append("/tmp")

    nltk.download("wordnet", download_dir = "/tmp")

    aspects_rec_movie = get_aspects(db_connection, top_item).sort_values('score', ascending=False)

    top_rec_aspects = get_n_aspects(5, aspects_rec_movie)
    max = 0
    word_p = ""
    word_r = ""
    movie_pro = 0

    for p_movie in profile_itens:
        aspects_profile_movie = get_aspects(db_connection, p_movie).sort_values('score', ascending=False)

        top_profile_aspects = get_n_aspects(5, aspects_profile_movie)
        for p_aspects in top_profile_aspects:
            for r_aspects in top_rec_aspects:
                sim = wn.wup_similarity(p_aspects, r_aspects)
                if sim is not None and sim > max and sim != 1: # TODO sim != 1
                    max = sim
                    movie_pro = p_movie
                    word_p = p_aspects.name().split('.')[0]
                    word_r = r_aspects.name().split('.')[0]

    if movie_pro == 0:
        mv_data = get_title(db_connection, profile_itens[0], top_item)
        return "Because you rated well the movie \"" + mv_data['title'][top_item] + "\" watch \"" + \
               mv_data['title'][profile_itens[0]] + "\""

    mv_data = get_title(db_connection, movie_pro, top_item)

    movie_pro_name = mv_data['title'][movie_pro]
    movie_rec_name = mv_data['title'][top_item]

    if word_p != word_r:
        sentence = "Because you rated well the movie \"" + movie_pro_name + "\" described as \"" \
                   + word_p + "\" watch \"" + movie_rec_name + "\" described with the similar word \"" + word_r + "\""
    else:
        sentence = "Because you rated well the movie \"" + movie_pro_name + "\" described as \"" \
                   + word_p + "\" watch \"" + movie_rec_name + "\" described with the same word"

    return sentence

def generate_explanations_compare(profile_itens: list, top_item: int):
    # nltk.download('wordnet')
    
    nltk.data.path.append("/tmp")

    nltk.download("wordnet", download_dir = "/tmp")

    aspects_rec_movie = get_aspects(db_connection, top_item).sort_values('score', ascending=False)

    if aspects_rec_movie.empty:
        top_rec_aspects = []
    else:
        top_rec_aspects = get_n_aspects(5, aspects_rec_movie)
    
    sim_m = pd.DataFrame(columns=['movie_id', 'word_p', 'word_r', 'sim'])
    max = 0
    word_p = ""
    word_r = ""
    movie_pro = 0

    for p_movie in profile_itens:
        aspects_profile_movie = get_aspects(db_connection, p_movie).sort_values('score', ascending=False)
        if aspects_profile_movie.empty:
            break

        top_profile_aspects = get_n_aspects(5, aspects_profile_movie)
        for p_aspects in top_profile_aspects:
            for r_aspects in top_rec_aspects:
                sim = wn.wup_similarity(p_aspects, r_aspects)
                if sim is not None and sim != 1:
                    word_p = p_aspects.name().split('.')[0]
                    word_r = r_aspects.name().split('.')[0]
                    sim_m.loc[len(sim_m)+1] = [p_movie, word_p, word_r, sim]
                    max = sim
                    movie_pro = p_movie

    if movie_pro == 0:
        mv_data = get_title(db_connection, profile_itens[0], top_item)
        return "Because you rated well the movie \"" + mv_data['title'][top_item] + "\" watch \"" + \
               mv_data['title'][profile_itens[0]] + "\"", mv_data['title'][top_item], mv_data['title'][profile_itens[0]]

    mv_first = sim_m.sort_values('sim', ascending=False).groupby('movie_id').head(5)
    mv_first = mv_first.groupby('movie_id')['sim'].mean().sort_values(ascending=False)
    mv_first = mv_first.index.tolist()[0]
    mv_data = get_title(db_connection, mv_first, top_item)

    movie_pro_name = mv_data['title'][mv_first]
    movie_rec_name = mv_data['title'][top_item]

    sim_m = sim_m[sim_m['movie_id'] == mv_first].sort_values('sim', ascending=False)[:3]
    movie_word_p = sim_m['word_p'].unique()
    movie_word_r = sim_m['word_r'].unique()

    sentence = "Because you watched \"" + movie_pro_name + "\", described as "
    
    if len(movie_word_p) > 1:
        words_p = join_words(movie_word_p)
        sentence += "\"" + words_p + "\", watch \"" + movie_rec_name + "\" "
    else:
        sentence += "\"" + movie_word_p[0] + "\", watch \"" + movie_rec_name + "\" "

    if len(movie_word_r) > 1:
        words_r = join_words(movie_word_r)
        sentence += ", described as similar words \"" + words_r + "\"."
    else:
        sentence += ", described as similar word \"" + movie_word_r[0] + "\"."

    return sentence, movie_pro_name, movie_rec_name

def generate_explanations_baseline(profile_itens, movie_rec, baseline_sim):
    baseline = baseline_sim.loc[movie_rec][profile_itens].sort_values(ascending = False)
    movie_pro = baseline.index[0]

    mv_data = get_title(db_connection, movie_pro, movie_rec)

    movie_pro_name = mv_data['title'][movie_pro]
    movie_rec_name = mv_data['title'][movie_rec]

    sentence = "Because you rated well the movie \"" + movie_pro_name + "\" watch \"" + movie_rec_name + "\""
    return sentence

def generate_explanations_AB(user_id: int, movies: list):
    movies = pd.DataFrame(movies)
    movies["justA"] = ""
    movies["justB"] = ""
    profile_itens = get_movies(db_connection, user_id)["movie_id"].tolist()

    # used_columns = ['user_id', 'movie_id', 'rating']
    # cols = pd.read_csv(os.environ['DATASET'] + "/user_rating.csv", usecols=used_columns)['movie_id'].unique()

    # baseline_sim = pd.read_csv(os.environ['DATASET'] + "/cosine_sim_matrix_5.csv", header=None)
    # baseline_sim.index = cols
    # baseline_sim.columns = cols

    # print(profile_itens)
    for index, row in movies.iterrows():
        sentence, m_p, m_r = generate_explanations_compare(profile_itens, row["movie_id"])
        movies["justA"][index] = sentence
        movies["justB"][index] = "Because you rated well the movie \"" + m_p + "\", watch \"" + m_r + "\"."
    
    return movies.to_json(orient="records")

