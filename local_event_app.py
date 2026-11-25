import io, os, socket, zipfile, json
from pathlib import Path
import streamlit as st
from matcher import find_matches
from utils import image_bytes_preview, make_qr

st.set_page_config(page_title='Event Photo Finder - Local HDD Mode', page_icon='📸', layout='wide')
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
CONFIG_FILE = Path(__file__).with_name('local_event_config.json')


def read_local_config():
    try:
        return json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}


def write_local_config(folder, event_name):
    CONFIG_FILE.write_text(json.dumps({'folder': folder, 'event_name': event_name}, indent=2), encoding='utf-8')


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


def browse_folder_windows():
    """Native Windows folder picker. Works only when Streamlit runs on the organizer's PC."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        selected = filedialog.askdirectory(title='Select event photo folder')
        root.destroy()
        return selected or ''
    except Exception as exc:
        st.error(f'Folder picker could not open: {exc}')
        return ''


def load_local_gallery(folder):
    root = Path(folder).expanduser()
    if not root.exists() or not root.is_dir():
        raise ValueError('Folder does not exist or is not a directory.')
    items = []
    for p in root.rglob('*'):
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
            try:
                data = p.read_bytes()
                preview = image_bytes_preview(data, max_side=700)
                items.append({'name': str(p.relative_to(root)), 'original': data, 'preview': preview})
            except Exception as e:
                st.warning(f'Could not load {p.name}: {e}')
    return items


params = st.query_params
is_guest = params.get('mode', '') == 'guest'
local_cfg = read_local_config()

if not is_guest:
    st.title('📸 Event Photo Finder — Local Event Setup')
    st.info('This mode reads photos directly from a folder on this computer, including internal drives, USB drives and mapped network drives. Guests need to connect to the same Wi-Fi network.')

    if 'local_folder' not in st.session_state:
        st.session_state['local_folder'] = local_cfg.get('folder', '')
    if 'local_event_name' not in st.session_state:
        st.session_state['local_event_name'] = local_cfg.get('event_name', 'Wedding Photo Gallery')

    event_name = st.text_input('Event name', key='local_event_name')
    st.subheader('Event photo folder')
    c1, c2 = st.columns([5, 1])
    with c1:
        folder = st.text_input('Folder path', key='local_folder', placeholder=r'C:\Users\YourName\Pictures\Wedding', label_visibility='collapsed')
    with c2:
        if st.button('📂 Browse', use_container_width=True):
            chosen = browse_folder_windows()
            if chosen:
                st.session_state['local_folder'] = chosen
                st.session_state.pop('local_scan_ok', None)
                st.rerun()

    if st.button('🔍 Scan photo folder', type='primary', use_container_width=True):
        if not folder.strip():
            st.error('Please browse and select a photo folder.')
        else:
            with st.spinner('Scanning folder and subfolders...'):
                try:
                    gallery = load_local_gallery(folder)
                    if not gallery:
                        st.warning('No supported image files were found in this folder.')
                    else:
                        st.session_state['local_gallery_count'] = len(gallery)
                        st.session_state['local_scan_ok'] = True
                        write_local_config(folder, event_name)
                        st.success(f'Folder scanned: {len(gallery)} images found. Photos remain on this computer.')
                except Exception as e:
                    st.session_state['local_scan_ok'] = False
                    st.error(str(e))

    if st.session_state.get('local_scan_ok'):
        st.success(f"Gallery ready: {st.session_state.get('local_gallery_count', 0)} images")

    st.markdown('---')
    st.subheader('📱 Guest access QR code')
    ip = lan_ip()
    guest_url = f'http://{ip}:8501/?mode=guest'
    st.write('Connect this laptop and guests’ phones to the same Wi-Fi network.')
    st.code(guest_url)
    st.image(make_qr(guest_url), caption='Scan with a phone connected to the same Wi-Fi', width=420)
    st.markdown(f'**Test guest page:** [Open guest page]({guest_url})')
    st.warning('Keep this local server running. If Windows Firewall asks, allow Python on Private networks only.')

else:
    st.title('📸 Find Your Event Photos')
    st.caption('Take a selfie with your camera or upload a selfie. Matching runs against the photo folder on the event host computer.')
    folder = local_cfg.get('folder', '')
    if not folder:
        st.error('The organizer has not configured the photo folder on the host laptop yet.')
        st.stop()
    event_name = local_cfg.get('event_name', 'Wedding Photo Gallery')
    st.subheader(event_name)

    # Keep both options: live camera capture and selfie upload.
    camera = st.camera_input('📷 Take Photo')
    uploads = st.file_uploader('Or upload selfie image(s)', type=['jpg', 'jpeg', 'png', 'webp'], accept_multiple_files=True)
    selfies = []
    if camera:
        selfies.append({'name': 'Camera selfie', 'bytes': camera.getvalue()})
    if uploads:
        selfies.extend({'name': f.name, 'bytes': f.getvalue()} for f in uploads)

    threshold = st.slider('Matching sensitivity', 0.20, 0.70, 0.40, 0.01, help='Lower is stricter; higher may increase false matches.')
    if selfies and st.button('🔎 Find My Photos', type='primary', use_container_width=True):
        try:
            with st.spinner('Loading photos from the event folder...'):
                images = load_local_gallery(folder)
            if not images:
                st.error('No supported photos found in the configured folder.')
            else:
                merged = {}
                all_errors = []
                progress = st.progress(0)
                for si, selfie in enumerate(selfies):
                    try:
                        matches, errs = find_matches(selfie['bytes'], images, threshold)
                        all_errors.extend(errs)
                        for m in matches:
                            if m['name'] not in merged or m['distance'] < merged[m['name']]['distance']:
                                merged[m['name']] = m
                    except Exception as e:
                        all_errors.append(f"{selfie['name']}: {e}")
                    progress.progress((si + 1) / len(selfies))
                progress.empty()
                results = sorted(merged.values(), key=lambda m: m['distance'])
                st.session_state['local_matches'] = results
                st.session_state['local_errors'] = all_errors
                st.session_state['local_total'] = len(images)
        except Exception as e:
            st.error(f'Gallery search failed: {e}')

    if 'local_matches' in st.session_state:
        matches = st.session_state['local_matches']
        errors = st.session_state.get('local_errors', [])
        st.markdown('---')
        st.subheader('🎉 Search Results')
        st.write(f"Gallery images scanned: {st.session_state.get('local_total', 0)} | Matches: {len(matches)}")
        if not matches:
            st.warning('No matching photos found. Try another selfie or sensitivity setting.')
        else:
            cols = st.columns(3)
            for i, m in enumerate(matches):
                with cols[i % 3]:
                    st.image(m['preview'], use_container_width=True)
                    st.caption(m['name'])
                    st.caption(f"Distance: {m['distance']:.4f}")
                    st.download_button('⬇️ Download photo', m['original'], file_name=Path(m['name']).name, mime='image/jpeg', key=f'local_download_{i}', use_container_width=True)
            if len(matches) > 1:
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
                    for m in matches:
                        z.writestr(m['name'], m['original'])
                st.download_button('📦 Download all matching photos', buf.getvalue(), file_name='my_event_photos.zip', mime='application/zip', use_container_width=True)
        if errors:
            with st.expander('Processing notes/errors'):
                for e in errors[:30]:
                    st.write(e)
