
import io, os, socket, zipfile, json
from pathlib import Path
import streamlit as st
from PIL import Image
from matcher import find_matches
from utils import image_bytes_preview, make_qr

st.set_page_config(
    page_title='Event Photo Finder - Local HDD Mode',
    page_icon='📸',
    layout='wide'
)

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
CONFIG_FILE = Path(__file__).with_name('local_event_config.json')


# ============================================================
# CONFIGURATION
# ============================================================

def read_local_config():
    try:
        return json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}


def write_local_config(folder, event_name):
    CONFIG_FILE.write_text(
        json.dumps(
            {'folder': folder, 'event_name': event_name},
            indent=2
        ),
        encoding='utf-8'
    )


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


# ============================================================
# WINDOWS FOLDER BROWSER
# ============================================================

def browse_local_folder():
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)

        selected_folder = filedialog.askdirectory(
            title="Select Event Photo Folder"
        )

        root.destroy()

        if selected_folder:
            st.session_state['local_folder_path'] = selected_folder

    except Exception as e:
        st.error(f"Unable to open folder browser: {e}")


# ============================================================
# PATH HANDLING
# ============================================================

def normalize_folder_path(folder):

    folder = str(folder).strip()

    if folder.startswith('"') and folder.endswith('"'):
        folder = folder[1:-1]

    if folder.startswith("'") and folder.endswith("'"):
        folder = folder[1:-1]

    folder = os.path.expandvars(folder)
    folder = os.path.expanduser(folder)
    folder = os.path.normpath(folder)

    return folder


# ============================================================
# LOCAL PHOTO GALLERY
# ============================================================

def load_local_gallery(folder):

    folder = normalize_folder_path(folder)
    root = Path(folder)

    if not os.path.exists(folder):
        raise ValueError(
            f"Folder does not exist:\n{folder}"
        )

    if not os.path.isdir(folder):
        raise ValueError(
            f"The selected path is not a folder:\n{folder}"
        )

    items = []

    for p in root.rglob('*'):

        if p.is_file() and p.suffix.lower() in IMAGE_EXTS:

            try:

                data = p.read_bytes()

                preview = image_bytes_preview(
                    data,
                    max_side=700
                )

                items.append({
                    'name': str(p.relative_to(root)),
                    'original': data,
                    'preview': preview
                })

            except Exception as e:

                st.warning(
                    f'Could not load {p.name}: {e}'
                )

    return items


# ============================================================
# APPLICATION MODE
# ============================================================

params = st.query_params
is_guest = params.get('mode', '') == 'guest'
local_cfg = read_local_config()


# ============================================================
# ORGANIZER / HOST PAGE
# ============================================================

if not is_guest:

    st.title('📸 Event Photo Finder — Local Event Setup')

    st.info(
        'This mode reads photos from folders on this computer, '
        'including internal drives, USB hard disks and mapped '
        'network drives. Guests must connect to the same Wi-Fi network.'
    )

    # --------------------------------------------------------
    # LOCAL PHOTO FOLDER
    # --------------------------------------------------------

    if 'local_folder_path' not in st.session_state:

        st.session_state['local_folder_path'] = (
            local_cfg.get('folder', '')
        )

    st.subheader('Local photo folder path')

    col1, col2 = st.columns([5, 1])

    with col1:

        folder = st.text_input(
            'Photo folder path',
            key='local_folder_path',
            placeholder=r'E:\Wedding Photos or C:\Users\YourName\Pictures\Wedding',
            label_visibility='collapsed'
        )

    with col2:

        st.button(
            '📁 Browse',
            on_click=browse_local_folder,
            use_container_width=True
        )

    st.caption(
        'Enter the folder path or click Browse to select '
        'your event photo folder.'
    )

    # --------------------------------------------------------
    # EVENT NAME
    # --------------------------------------------------------

    event_name = st.text_input(
        'Event name',
        value=st.session_state.get(
            'local_event_name',
            local_cfg.get('event_name', 'Wedding Photo Gallery')
        ),
        key='local_event_name'
    )

    # --------------------------------------------------------
    # SCAN PHOTO FOLDER
    # --------------------------------------------------------

    if st.button(
        'Scan photo folder',
        type='primary'
    ):

        folder = st.session_state.get(
            'local_folder_path',
            ''
        )

        if not folder.strip():

            st.error('Select or enter a folder path first.')

        else:

            with st.spinner(
                'Scanning folder and subfolders...'
            ):

                try:

                    folder = normalize_folder_path(folder)

                    gallery = load_local_gallery(folder)

                    st.session_state['local_gallery_count'] = (
                        len(gallery)
                    )

                    st.session_state['local_scan_ok'] = True

                    write_local_config(
                        folder,
                        event_name
                    )

                    st.success(
                        f'Folder scanned: {len(gallery)} '
                        'supported images found.'
                    )

                except Exception as e:

                    st.session_state['local_scan_ok'] = False

                    st.error(str(e))

    # --------------------------------------------------------
    # SCAN STATUS
    # --------------------------------------------------------

    if st.session_state.get('local_scan_ok'):

        st.success(
            f"Ready: "
            f"{st.session_state.get('local_gallery_count', 0)} images"
        )

    # --------------------------------------------------------
    # QR CODE
    # --------------------------------------------------------

    st.markdown('---')

    st.subheader('📺 QR code for the extended display')

    ip = lan_ip()

    guest_url = f'http://{ip}:8501/?mode=guest'

    st.write(
        'Connect the laptop and guests’ phones to the same Wi-Fi network. '
        'The guest page will use this laptop as the photo-search server.'
    )

    st.code(guest_url)

    qr = make_qr(guest_url)

    st.image(
        qr,
        caption='Scan this QR code with a phone connected to the same Wi-Fi network',
        width=420
    )

    st.markdown(
        '**To show this QR code on your TV/second screen:** '
        'move the browser window to the extended display and press `F11` for full screen.'
    )

    st.warning(
        'Keep this local server running and do not close the terminal '
        'while guests are searching.'
    )

    st.markdown('---')

    st.subheader('How to open the guest page on this laptop')

    st.markdown(
        f'Use [the guest page]({guest_url}) to test. '
        'If Windows Firewall asks whether Python/Streamlit may '
        'communicate on your network, allow it on **Private networks** only.'
    )


# ============================================================
# GUEST PAGE
# ============================================================

else:

    st.title('📸 Find Your Event Photos')

    st.caption(
        'Your selfie is processed on the event laptop. '
        'Connect to the same Wi-Fi as the photo gallery host.'
    )

    folder = local_cfg.get('folder', '')

    if not folder:

        st.error(
            'The organizer has not configured the photo folder '
            'on the host laptop yet.'
        )

        st.stop()

    event_name = local_cfg.get(
        'event_name',
        'Wedding Photo Gallery'
    )

    st.subheader(event_name)

    # --------------------------------------------------------
    # CAMERA ONLY - NO SELFIE FILE BROWSER
    # --------------------------------------------------------

    camera = st.camera_input('Take a selfie')

    selfies = []

    if camera:

        selfies.append({
            'name': 'Camera selfie',
            'bytes': camera.getvalue()
        })

    # --------------------------------------------------------
    # MATCHING SENSITIVITY
    # --------------------------------------------------------

    threshold = st.slider(
        'Matching sensitivity',
        0.20,
        0.70,
        0.40,
        0.01,
        help='Lower is stricter; higher may increase false matches.'
    )

    # --------------------------------------------------------
    # SEARCH
    # --------------------------------------------------------

    if selfies and st.button(
        '🔎 Find My Photos',
        type='primary',
        use_container_width=True
    ):

        try:

            with st.spinner('Loading local photos...'):

                images = load_local_gallery(folder)

            if not images:

                st.error(
                    'No supported photos found in the configured folder.'
                )

            else:

                merged = {}
                all_errors = []
                progress = st.progress(0)

                for si, selfie in enumerate(selfies):

                    try:

                        matches, errs = find_matches(
                            selfie['bytes'],
                            images,
                            threshold
                        )

                        all_errors.extend(errs)

                        for m in matches:

                            if (
                                m['name'] not in merged
                                or m['distance']
                                < merged[m['name']]['distance']
                            ):

                                merged[m['name']] = m

                    except Exception as e:

                        all_errors.append(
                            f"{selfie['name']}: {e}"
                        )

                    progress.progress(
                        (si + 1) / len(selfies)
                    )

                progress.empty()

                results = sorted(
                    merged.values(),
                    key=lambda m: m['distance']
                )

                st.session_state['local_matches'] = results

                st.session_state['local_errors'] = all_errors

                st.session_state['local_total'] = len(images)

        except Exception as e:

            st.error(
                f'Gallery search failed: {e}'
            )

    # --------------------------------------------------------
    # RESULTS
    # --------------------------------------------------------

    if 'local_matches' in st.session_state:

        matches = st.session_state['local_matches']

        errors = st.session_state.get(
            'local_errors',
            []
        )

        st.markdown('---')

        st.subheader('🎉 Search Results')

        st.write(
            f"Gallery images scanned: "
            f"{st.session_state.get('local_total', 0)} "
            f"| Matches: {len(matches)}"
        )

        # ----------------------------------------------------
        # NO MATCHES
        # ----------------------------------------------------

        if not matches:

            st.warning(
                'No matching photos found. '
                'Try another selfie or sensitivity setting.'
            )

        # ----------------------------------------------------
        # MATCHES
        # ----------------------------------------------------

        else:

            cols = st.columns(3)

            for i, m in enumerate(matches):

                with cols[i % 3]:

                    st.image(
                        m['preview'],
                        use_container_width=True
                    )

                    st.caption(m['name'])

                    st.caption(
                        f"Distance: {m['distance']:.4f}"
                    )

                    st.download_button(
                        '⬇️ Download photo',
                        m['original'],
                        file_name=Path(m['name']).name,
                        mime='image/jpeg',
                        key=f'local_download_{i}',
                        use_container_width=True
                    )

            # ------------------------------------------------
            # DOWNLOAD ZIP
            # ------------------------------------------------

            if len(matches) > 1:

                buf = io.BytesIO()

                with zipfile.ZipFile(
                    buf,
                    'w',
                    zipfile.ZIP_DEFLATED
                ) as z:

                    for m in matches:

                        z.writestr(
                            m['name'],
                            m['original']
                        )

                st.download_button(
                    '📦 Download all matching photos',
                    buf.getvalue(),
                    file_name='my_event_photos.zip',
                    mime='application/zip',
                    use_container_width=True
                )

        # ----------------------------------------------------
        # PROCESSING NOTES
        # ----------------------------------------------------

        if errors:

            with st.expander('Processing notes/errors'):

                for e in errors[:30]:

                    st.write(e)
