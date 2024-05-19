from django.shortcuts import render, redirect
from marmut_function.general import *
import marmut_function.general as sql
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt

# CRUD KELOLA ALBUM & SONG untuk Artist/Songwriter
# View untuk menampilkan halaman pembuatan album untuk artist
def create_album_artist(request):
    if request.method == "GET":
        # Mendapatkan daftar label yang terdaftar pada Marmut
        labels = query_result("SELECT id, nama FROM LABEL")
        label_list = [{'id': label[0], 'nama': label[1]} for label in labels]

        # Mendapatkan daftar genre yang terdaftar pada Marmut
        genres = query_result("SELECT DISTINCT genre FROM GENRE")
        genre_list = [{'genre': genre[0]} for genre in genres]

        return render(request, 'create_album.html', {'labels': label_list, 'genres': genre_list})

    if request.method == "POST":
        judul_album = request.POST.get('judul_album')
        label_id = request.POST.get('label')
        judul_lagu = request.POST.get('judul_lagu')
        durasi = request.POST.get('durasi')
        genre_ids = request.POST.getlist('genre')
        songwriter_ids = request.POST.getlist('songwriter')

        # Asumsi user logged in sebagai artist atau songwriter
        user_email = request.session.get('email')
        user = query_result(f"SELECT id, role FROM AKUN WHERE email = '{user_email}'")[0]

        if user['role'] == 'artist':
            artist_id = user['id']
        else:
            artist_id = request.POST.get('artist')

        try:
            # Buat album
            album_id = query_add_returning(
                f"""
                INSERT INTO ALBUM (judul, id_label)
                VALUES ('{judul_album}', '{label_id}')
                RETURNING id
                """
            )[0][0]

            # Buat konten lagu
            song_id = query_add_returning(
                f"""
                INSERT INTO KONTEN (judul, tanggal_rilis, tahun, durasi)
                VALUES ('{judul_lagu}', CURRENT_DATE, EXTRACT(YEAR FROM CURRENT_DATE), '{durasi}')
                RETURNING id
                """
            )[0][0]

            # Tambahkan lagu ke album
            query_add(
                f"""
                INSERT INTO SONG (id_konten, id_album, id_artist)
                VALUES ('{song_id}', '{album_id}', '{artist_id}')
                """
            )

            # Tambahkan genre
            for genre_id in genre_ids:
                query_add(
                    f"""
                    INSERT INTO GENRE (id_konten, genre)
                    VALUES ('{song_id}', '{genre_id}')
                    """
                )

            # Tambahkan songwriter
            for songwriter_id in songwriter_ids:
                query_add(
                    f"""
                    INSERT INTO SONGWRITER_WRITE_SONG (id_song, id_songwriter)
                    VALUES ('{song_id}', '{songwriter_id}')
                    """
                )

            return redirect('kelola_album_song:list_album_crud')

        except Exception as e:
            return HttpResponseBadRequest(f"Error: {str(e)}")

def list_album_crud(request):
    user_email = request.session.get('email')

    # Cek apakah email ada di tabel artist, songwriter, atau label
    is_artist = query_result(f"SELECT 1 FROM artist WHERE email_akun = '{user_email}'")
    is_songwriter = query_result(f"SELECT 1 FROM songwriter WHERE email_akun = '{user_email}'")
    is_label = query_result(f"SELECT 1 FROM label WHERE email = '{user_email}'")

    albums = []

    if is_artist:
        # Query untuk artist
        albums = query_result(
            f"""
            SELECT A.id, A.judul, L.nama AS label_name, COUNT(S.id_konten), SUM(K.durasi)
            FROM ALBUM A
            LEFT JOIN SONG S on A.id = S.id_album
            LEFT JOIN KONTEN K on S.id_konten = K.id
            LEFT JOIN LABEL L on A.id_label = L.id
            WHERE S.id_artist = (SELECT id FROM artist WHERE email_akun = '{user_email}')
            GROUP BY A.id, A.judul, L.nama
            """
        )
    elif is_songwriter:
        # Query untuk songwriter
        albums = query_result(
            f"""
            SELECT A.id, A.judul, L.nama AS label_name, COUNT(S.id_konten), SUM(K.durasi)
            FROM ALBUM A
            LEFT JOIN SONG S on A.id = S.id_album
            LEFT JOIN KONTEN K on S.id_konten = K.id
            LEFT JOIN LABEL L on A.id_label = L.id
            JOIN SONGWRITER_WRITE_SONG SW ON S.id_konten = SW.id_song
            WHERE SW.id_songwriter = (SELECT id FROM songwriter WHERE email_akun = '{user_email}')
            GROUP BY A.id, A.judul, L.nama
            """
        )
    elif is_label:
        # Query untuk label
        albums = query_result(
            f"""
            SELECT A.id, A.judul, L.nama AS label_name, COUNT(S.id_konten), SUM(K.durasi)
            FROM ALBUM A
            LEFT JOIN SONG S on A.id = S.id_album
            LEFT JOIN KONTEN K on S.id_konten = K.id
            LEFT JOIN LABEL L on A.id_label = L.id
            WHERE A.id_label = (SELECT id FROM label WHERE email = '{user_email}')
            GROUP BY A.id, A.judul, L.nama
            """
        )
    else:
        return HttpResponseBadRequest("Invalid user role or user not found.")

    album_list = [{'id': album[0], 'judul': album[1], 'label_name': album[2], 'jumlah_lagu': album[3], 'total_durasi': album[4]} for album in albums]

    return render(request, 'list_album_crud.html', {'albums': album_list})

def list_songs_in_album_crud(request, user_id, album_id):
    album = query_result(f"SELECT judul FROM ALBUM WHERE id = '{album_id}'")[0]
    songs = query_result(
        f"""
        SELECT 
            S.id_konten AS song_id, 
            K.judul AS song_title, 
            K.durasi AS duration, 
            S.total_play AS total_play, 
            S.total_download AS total_download
        FROM 
            SONG S
        JOIN 
            KONTEN K ON S.id_konten = K.id
        WHERE 
            S.id_album = '{album_id}'
        """
    )

    song_list = [{'id': song[0], 'judul': song[1], 'durasi': song[2], 'total_play': song[3], 'total_download': song[4]} for song in songs]

    return render(request, 'list_song_crud.html', {'songs': song_list, 'album_id': album_id, 'judul_album': album[0]})


def delete_album_artist(request, album_id):
    try:
        # Hapus referensi dari tabel royalti
        query_add(f"DELETE FROM royalti WHERE id_song IN (SELECT id_konten FROM SONG WHERE id_album = '{album_id}')")
        
        # Hapus referensi dari tabel songwriter_write_song
        query_add(f"DELETE FROM SONGWRITER_WRITE_SONG WHERE id_song IN (SELECT id_konten FROM SONG WHERE id_album = '{album_id}')")
        
        # Hapus referensi dari tabel downloaded_song
        query_add(f"DELETE FROM downloaded_song WHERE id_song IN (SELECT id_konten FROM SONG WHERE id_album = '{album_id}')")
        
        # Hapus referensi dari tabel akun_play_song
        query_add(f"DELETE FROM akun_play_song WHERE id_song IN (SELECT id_konten FROM SONG WHERE id_album = '{album_id}')")
        
        # Hapus referensi dari tabel playlist_song
        query_add(f"DELETE FROM playlist_song WHERE id_song IN (SELECT id_konten FROM SONG WHERE id_album = '{album_id}')")
        
        # Hapus referensi dari tabel genre
        query_add(f"DELETE FROM genre WHERE id_konten IN (SELECT id_konten FROM SONG WHERE id_album = '{album_id}')")
        
        # Hapus lagu dari tabel song
        query_add(f"DELETE FROM SONG WHERE id_album = '{album_id}'")
        
        # Hapus konten dari tabel konten
        query_add(f"DELETE FROM KONTEN WHERE id IN (SELECT id_konten FROM SONG WHERE id_album = '{album_id}')")
        
        # Hapus album dari tabel album
        query_add(f"DELETE FROM ALBUM WHERE id = '{album_id}'")
        
        return redirect('kelola_album_song:list_album_crud')
    except Exception as e:
        return HttpResponseBadRequest(f"Error: {str(e)}")


def delete_song_from_album_artist(request, album_id, song_id):
    try:
        # Hapus referensi dari tabel songwriter_write_song
        query_add(f"DELETE FROM SONGWRITER_WRITE_SONG WHERE id_song = '{song_id}'")

        # Hapus referensi dari tabel lain yang memiliki foreign key ke id_konten
        query_add(f"DELETE FROM downloaded_song WHERE id_song = '{song_id}'")
        query_add(f"DELETE FROM royalti WHERE id_song = '{song_id}'")
        query_add(f"DELETE FROM akun_play_song WHERE id_song = '{song_id}'")
        query_add(f"DELETE FROM playlist_song WHERE id_song = '{song_id}'")
        query_add(f"DELETE FROM genre WHERE id_konten = '{song_id}'")
        
        # Hapus lagu dari tabel song
        query_add(f"DELETE FROM SONG WHERE id_konten = '{song_id}'")

        # Hapus konten dari tabel konten
        query_add(f"DELETE FROM KONTEN WHERE id = '{song_id}'")

        return redirect('kelola_album_song:list_songs_in_album_crud', album_id=album_id)
    except Exception as e:
        return HttpResponseBadRequest(f"Error: {str(e)}")

def add_song_to_album_artist(request, album_id):
    if request.method == "GET":
        # Mendapatkan data yang diperlukan
        artists = query_result("SELECT id, email_akun FROM ARTIST")
        genres = query_result("SELECT DISTINCT genre FROM GENRE")
        songwriters = query_result("SELECT id, email_akun FROM SONGWRITER")

        artist_list = [{'id': artist[0], 'email_akun': artist[1]} for artist in artists]
        genre_list = [{'genre': genre[0]} for genre in genres]
        songwriter_list = [{'id': songwriter[0], 'email_akun': songwriter[1]} for songwriter in songwriters]

        return render(request, 'create_song.html', {
            'artists': artist_list,
            'genres': genre_list,
            'songwriters': songwriter_list,
            'album_id': album_id
        })

    if request.method == "POST":
        judul_lagu = request.POST.get('judul_lagu')
        durasi = request.POST.get('durasi')
        genre_ids = request.POST.getlist('genre')
        songwriter_ids = request.POST.getlist('songwriter')

        user_email = request.session.get('email')
        user = query_result(f"SELECT id, role FROM AKUN WHERE email = '{user_email}'")[0]

        if user['role'] == 'artist':
            artist_id = user['id']
        else:
            artist_id = request.POST.get('artist')

        try:
            # Buat konten lagu
            song_id = query_add_returning(
                f"""
                INSERT INTO KONTEN (judul, tanggal_rilis, tahun, durasi)
                VALUES ('{judul_lagu}', CURRENT_DATE, EXTRACT(YEAR FROM CURRENT_DATE), '{durasi}')
                RETURNING id
                """
            )[0][0]

            # Tambahkan lagu ke album
            query_add(
                f"""
                INSERT INTO SONG (id_konten, id_album, id_artist)
                VALUES ('{song_id}', '{album_id}', '{artist_id}')
                """
            )

            # Tambahkan genre
            for genre_id in genre_ids:
                query_add(
                    f"""
                    INSERT INTO GENRE (id_konten, genre)
                    VALUES ('{song_id}', '{genre_id}')
                    """
                )

            # Tambahkan songwriter
            for songwriter_id in songwriter_ids:
                query_add(
                    f"""
                    INSERT INTO SONGWRITER_WRITE_SONG (id_song, id_songwriter)
                    VALUES ('{song_id}', '{songwriter_id}')
                    """
                )

            return redirect('kelola_album_song:list_album_crud')

        except Exception as e:
            return HttpResponseBadRequest(f"Error: {str(e)}")

# View untuk menampilkan detail lagu
def detail_song(request, song_id):
    song = query_result(f"""
        SELECT K.judul, K.durasi, S.total_play, S.total_download
        FROM SONG S
        JOIN KONTEN K on S.id_konten = K.id
        WHERE S.id_konten = '{song_id}'
    """)[0]

    song_details = {
        'judul': song[0],
        'durasi': song[1],
        'total_play': song[2],
        'total_download': song[3]
    }

    return render(request, 'create_song.html', {'song': song_details})

# RD KELOLA ALBUM & SONG untuk Label
def list_album_rd(request):
    user_email = request.session.get('email')
    user = query_result(f"SELECT id, role FROM AKUN WHERE email = '{user_email}'")[0]

    albums = query_result(
        f"""
        SELECT A.id, A.judul, L.nama, COUNT(S.id_konten), SUM(K.durasi)
        FROM ALBUM A
        JOIN LABEL L on A.id_label = L.id
        LEFT JOIN SONG S on A.id = S.id_album
        LEFT JOIN KONTEN K on S.id_konten = K.id
        WHERE L.id = '{user['id']}'
        GROUP BY A.id, A.judul, L.nama
        """
    )

    album_list = [{'id': album[0], 'judul': album[1], 'label': album[2], 'jumlah_lagu': album[3], 'total_durasi': album[4]} for album in albums]

    return render(request, 'list_album_rd.html', {'albums': album_list})

def list_songs_in_album_rd(request, album_id):
    songs = query_result(
        f"""
        SELECT K.judul, K.durasi, S.total_play, S.total_download
        FROM SONG S
        JOIN KONTEN K on S.id_konten = K.id
        WHERE S.id_album = '{album_id}'
        """
    )

    song_list = [{'judul': song[0], 'durasi': song[1], 'total_play': song[2], 'total_download': song[3]} for song in songs]

    return render(request, 'list_song_rd.html', {'songs': song_list, 'album_id': album_id})

def list_albums_by_artist_or_songwriter(request, user_id):
    user_email = request.session.get('email')

    # Cek apakah user_id ada di tabel artist atau songwriter
    is_artist = query_result(f"SELECT 1 FROM artist WHERE id = '{user_id}'")
    is_songwriter = query_result(f"SELECT 1 FROM songwriter WHERE id = '{user_id}'")

    albums = []

    if is_artist:
        # Query untuk artist
        albums = query_result(
            f"""
            SELECT A.id, A.judul, L.nama AS label_name, COUNT(S.id_konten), SUM(K.durasi)
            FROM ALBUM A
            LEFT JOIN SONG S on A.id = S.id_album
            LEFT JOIN KONTEN K on S.id_konten = K.id
            LEFT JOIN LABEL L on A.id_label = L.id
            WHERE S.id_artist = '{user_id}'
            GROUP BY A.id, A.judul, L.nama
            """
        )
    elif is_songwriter:
        # Query untuk songwriter
        albums = query_result(
            f"""
            SELECT A.id, A.judul, L.nama AS label_name, COUNT(S.id_konten), SUM(K.durasi)
            FROM ALBUM A
            LEFT JOIN SONG S on A.id = S.id_album
            LEFT JOIN KONTEN K on S.id_konten = K.id
            LEFT JOIN LABEL L on A.id_label = L.id
            JOIN SONGWRITER_WRITE_SONG SW ON S.id_konten = SW.id_song
            WHERE SW.id_songwriter = '{user_id}'
            GROUP BY A.id, A.judul, L.nama
            """
        )
    else:
        return HttpResponseBadRequest("Invalid user role or user not found.")

    album_list = [{'id': album[0], 'judul': album[1], 'label_name': album[2], 'jumlah_lagu': album[3], 'total_durasi': album[4], 'user_id': user_id} for album in albums]

    return render(request, 'list_album_crud.html', {'albums': album_list})
