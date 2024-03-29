import numpy as np
import pandas as pd
from src.connection import db_connection
import src.users as users
import src.explanation as exp
import src.omdb as omdb
import json
import os

def get_movies(conn, imdb: list):
    imdb = [i[2:] for i in imdb]
    ids = ",".join(imdb)
    stmt = 'SELECT movie_id, imdbID FROM MOVIE WHERE imdbID in ({0})'.format(ids)
    return pd.read_sql(stmt, con=conn, index_col='movie_id')

def get_movies_data(conn, movie_id: list):
    ids = ",".join(str(i) for i in movie_id)
    return pd.read_sql('SELECT * FROM MOVIE WHERE movie_id in ({0})'.format(ids), con=conn)

def update_movie_poster(movie_id, poster):
    with db_connection.connect() as conn:
        with conn.begin():
            conn.execute(update_movie_poster_stmt(movie_id, poster))

def update_movie_poster_stmt(movie_id, poster):
    return "UPDATE MOVIE SET poster = '{0}' WHERE movie_id = {1}".format(poster, movie_id)

def insert_reclist1(user_id):
    with db_connection.connect() as conn:
        with conn.begin():
            result = conn.execute(insert_reclist1_stmt(user_id)).lastrowid
    return result

def insert_reclist1_stmt(user_id):
    return "INSERT INTO RECLIST1 (user_id) VALUES({0})".format(user_id)

def insert_reclist1movie(reclist1_id, movie: list):
    with db_connection.connect() as conn:
        with conn.begin():
            for m in movie:
                conn.execute(insert_reclist1movie_stmt(reclist1_id, m))

def insert_reclist1movie_stmt(reclist1_id, movie_id):
    return "INSERT INTO RECLIST1MOVIE (reclist1_id, movie_id) VALUES({0}, {1})".format(reclist1_id, movie_id)

def insert_reclist2(user_id):
    with db_connection.connect() as conn:
        with conn.begin():
            result = conn.execute(insert_reclist2_stmt(user_id)).lastrowid
    return result

def insert_reclist2_stmt(user_id):
    return "INSERT INTO RECLIST2 (user_id) VALUES({0})".format(user_id)

def insert_reclist2movie(reclist2_id, movie: list):
    with db_connection.connect() as conn:
        with conn.begin():
            for m in movie:
                conn.execute(insert_reclist2movie_stmt(reclist2_id, m))

def insert_reclist2movie_stmt(reclist2_id, movie_id):
    return "INSERT INTO RECLIST2MOVIE (reclist2_id, movie_id) VALUES({0}, {1})".format(reclist2_id, movie_id)

def calculate_prediction(k, movie, profile, sim_m):
    n = 0
    i = 0
    total = 0

    sim = sim_m.loc[movie][:]
    sim.loc[movie] = 0
    sim = sim.sort_values(ascending=False)
    while n < k and i < len(sim) - 1:
        neig = sim.index[i]
        if neig in profile.index:
            total = total + sim.iloc[i]
            n = n + 1
        i = i + 1

    return total


def generate_rec(number, k, u_row: pd.Series, sim_m: pd.DataFrame):
    profile = u_row[u_row == 1]
    prediction = u_row[u_row == 0]
    for m in prediction.index:
        prediction.loc[m] = calculate_prediction(k, m, profile, sim_m)

    prediction = prediction.sort_values(ascending=False)
    return prediction[:number].tolist(), prediction[:number].index

def recommendation(user_id, movies):

    used_columns = ['user_id', 'movie_id', 'rating']

    cols = pd.read_csv(os.environ['DATASET'] + "/user_rating.csv", usecols=used_columns)['movie_id'].unique()

    profile = pd.DataFrame(0, index=[1], columns=cols)

    movies = get_movies(db_connection, movies).index
    
    users.insert_user_movie(user_id, movies.tolist())

    profile[movies] = 1

    semantic_sim = pd.read_csv(os.environ['DATASET'] + "/sim_matrix.csv", header=None)
    semantic_sim.index = cols
    semantic_sim.columns = cols

    response_semantic, idx_semantic = generate_rec(5, 5, profile.loc[1], semantic_sim)

    rec_semantic = get_movies_data(db_connection, idx_semantic.tolist())
    rec_semantic['imdbID'] = rec_semantic['imdbID'].map('tt{0:07d}'.format)

    reclist1_id = insert_reclist1(user_id)
    insert_reclist1movie(reclist1_id, rec_semantic["movie_id"].tolist())

    semantic = json.loads(rec_semantic.to_json(orient="records"))
    return { "reclist1_id": reclist1_id, "semantic" : semantic } 

def baseline(user_id, movies):

    used_columns = ['user_id', 'movie_id', 'rating']

    cols = pd.read_csv(os.environ['DATASET'] + "/user_rating.csv", usecols=used_columns)['movie_id'].unique()

    profile = pd.DataFrame(0, index=[1], columns=cols)

    movies = get_movies(db_connection, movies).index

    profile[movies] = 1

    baseline_sim = pd.read_csv(os.environ['DATASET'] + "/cosine_sim_matrix_5.csv", header=None)
    baseline_sim.index = cols
    baseline_sim.columns = cols

    response_baseline, idx_baseline = generate_rec(5, 5, profile.loc[1], baseline_sim)

    rec_baseline = get_movies_data(db_connection, idx_baseline.tolist())
    rec_baseline['imdbID'] = rec_baseline['imdbID'].map('tt{0:07d}'.format)

    reclist2_id = insert_reclist2(user_id)
    insert_reclist2movie(reclist2_id, rec_baseline["movie_id"].tolist())
    baseline = json.loads(rec_baseline.to_json(orient="records"))
    return { "baseline": baseline, "reclist2_id": reclist2_id } 