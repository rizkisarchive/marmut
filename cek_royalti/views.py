from django.shortcuts import render
from django.http import HttpResponse, HttpResponseBadRequest
from marmut_function.general import query_result

def calculate_royalties(request, user_id, user_type):
    # Tentukan tabel dan kolom berdasarkan jenis pengguna
    user_table = user_column = None
    if user_type == 'artist':
        user_table = 'artist'
        user_column = 'id_artist'
    elif user_type == 'songwriter':
        user_table = 'songwriter'
        user_column = 'id_songwriter'
    elif user_type == 'label':
        user_table = 'label'
        user_column = 'id_label'
    else:
        return HttpResponse('Invalid user type', status=400)

    # Ambil informasi pengguna
    user_info = query_result(f"SELECT * FROM {user_table} WHERE id = '{user_id}'")
    if not user_info:
        return HttpResponse('User not found', status=404)

    # Ambil data lagu dan hitung royalti
    query = None
    if user_type == 'songwriter':
        query = f"""
            SELECT 
                k.judul AS title,
                a.judul AS album_title,
                s.total_play AS plays,
                s.total_download AS downloads,
                phc.rate_royalti AS royalty_rate,
                (s.total_play * phc.rate_royalti) AS total_royalty,
                sw.id AS user_id
            FROM 
                SONG s
            JOIN 
                KONTEN k ON s.id_konten = k.id
            JOIN 
                ALBUM a ON s.id_album = a.id
            JOIN 
                ROYALTI r ON r.id_song = s.id_konten
            JOIN 
                PEMILIK_HAK_CIPTA phc ON r.id_pemilik_hak_cipta = phc.id
            JOIN 
                SONGWRITER_WRITE_SONG sws ON s.id_konten = sws.id_song
            JOIN 
                SONGWRITER sw ON sws.id_songwriter = sw.id
            WHERE 
                sw.id = '{user_id}'
        """
    elif user_type == 'label':
        query = f"""
            SELECT 
                k.judul AS title,
                a.judul AS album_title,
                s.total_play AS plays,
                s.total_download AS downloads,
                phc.rate_royalti AS royalty_rate,
                (s.total_play * phc.rate_royalti) AS total_royalty,
                l.id AS user_id
            FROM 
                SONG s
            JOIN 
                KONTEN k ON s.id_konten = k.id
            JOIN 
                ALBUM a ON s.id_album = a.id
            JOIN 
                ROYALTI r ON r.id_song = s.id_konten
            JOIN 
                PEMILIK_HAK_CIPTA phc ON r.id_pemilik_hak_cipta = phc.id
            JOIN 
                LABEL l ON a.id_label = l.id
            WHERE 
                l.id = '{user_id}'
        """
    else:
        query = f"""
            SELECT 
                k.judul AS title,
                a.judul AS album_title,
                s.total_play AS plays,
                s.total_download AS downloads,
                phc.rate_royalti AS royalty_rate,
                (s.total_play * phc.rate_royalti) AS total_royalty,
                ar.id AS user_id
            FROM 
                SONG s
            JOIN 
                KONTEN k ON s.id_konten = k.id
            JOIN 
                ALBUM a ON s.id_album = a.id
            JOIN 
                ROYALTI r ON r.id_song = s.id_konten
            JOIN 
                PEMILIK_HAK_CIPTA phc ON r.id_pemilik_hak_cipta = phc.id
            JOIN 
                ARTIST ar ON s.id_artist = ar.id
            WHERE 
                ar.id = '{user_id}'
        """

    songs = query_result(query)

    # Debugging output to check the structure of the returned songs
    for song in songs:
        print(song)  # This will print the tuple structure of each song

    # Validate song tuples length before accessing indices
    for song in songs:
        if len(song) < 7:
            return HttpResponseBadRequest(f"Invalid song data: {song}")

    total_royalty = sum(song[5] for song in songs)  # Menjumlahkan kolom total_royalty

    context = {
        'user': user_info[0],
        'songs': [
            {
                'title': song[0],
                'album_title': song[1],
                'plays': song[2],
                'downloads': song[3],
                'royalty_rate': song[4],
                'total_royalty': song[5],
                'user_id': song[6]  # Adding user_id to context
            }
            for song in songs
        ],
        'total_royalty': total_royalty
    }
    return render(request, 'cek_royalti/royalty.html', context)
