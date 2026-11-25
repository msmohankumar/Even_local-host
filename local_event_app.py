import io, os, socket, zipfile, json
from pathlib import Path
import streamlit as st
from PIL import Image
from matcher import find_matches
from utils import image_bytes_preview, make_qr

st.set_page_config(page_title='Event Photo Finder - Local HDD Mode', page_icon='📸', layout='wide')
IMAGE_EXTS = {'.jpg','.jpeg','.png','.webp','.bmp'}
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
        s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('8.8.8.8',80)); ip=s.getsockname()[0]; s.close(); return ip
    except Exception: return '127.0.0.1'


def normalize_folder_path(folder):
    cleaned = str(folder or '').strip().strip('\"').strip("'")
    cleaned = os.path.expandvars(os.path.expanduser(cleaned))
    return os.path.normpath(cleaned)


def browse_for_folder():
    # tkinter folder dialog is opened on the host laptop, not on guest phones.
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes('-topmost', True)
        except Exception:
            pass
        selected = filedialog.askdirectory(title='Select the event photo folder')
        root.destroy()
        return selected or ''
    except Exception as e:
        st.error(f'Unable to open the folder browser: {e}')
        return ''


def load_local_gallery(folder):
    cleaned = normalize_folder_path(folder)
    root = Path(cleaned)
    if not cleaned or not root.exists() or not root.is_dir():
        raise ValueError(f'Folder not found or inaccessible: {cleaned}')
    items=[]
    try:
        for p in root.rglob('*'):
            if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
                try:
                    data=p.read_bytes()
                    preview=image_bytes_preview(data, max_side=700)
                    items.append({'name':str(p.relative_to(root)), 'original':data, 'preview':preview})
                except Exception as e:
                    st.warning(f'Could not load {p.name}: {e}')
    except Exception as e:
        raise ValueError(f'Error scanning folder {cleaned}: {e}')
    return items


params=st.query_params
is_guest=params.get('mode','')=='guest'
local_cfg=read_local_config()

if not is_guest:
    st.title('📸 Event Photo Finder — Local Event Setup')
    st.info('This mode reads photos from folders on this computer, including internal drives, USB hard disks and mapped network drives. Guests must connect to the same Wi-Fi network.')
    folder_col, browse_col = st.columns([5, 1])
    with folder_col:
        folder=st.text_input('Photo folder path', value=st.session_state.get('local_folder', ''), placeholder=r'E:\Wedding Photos or C:\Users\YourName\Pictures\Wedding', key='local_folder_input')
    with browse_col:
        st.markdown(' ')
        if st.button('📁 Browse', use_container_width=True):
            chosen_folder = browse_for_folder()
            if chosen_folder:
                st.session_state['local_folder_input'] = chosen_folder
                st.session_state['local_folder'] = chosen_folder
                st.rerun()
    st.session_state['local_folder']=folder
    event_name=st.text_input('Event name', value=st.session_state.get('local_event_name','Wedding Photo Gallery'))
    if st.button('Scan photo folder', type='primary'):
        if not folder.strip(): st.error('Enter a folder path first.')
        else:
            with st.spinner('Scanning folder and subfolders...'):
                try:
                    folder=normalize_folder_path(folder)
                    gallery=load_local_gallery(folder)
                    st.session_state['local_gallery_count']=len(gallery)
                    st.session_state['local_scan_ok']=True
                    write_local_config(folder, event_name)
                    st.success(f'Folder scanned: {len(gallery)} supported images found.')
                except Exception as e:
                    st.session_state['local_scan_ok']=False; st.error(str(e))
    if st.session_state.get('local_scan_ok'):
        st.success(f"Ready: {st.session_state.get('local_gallery_count',0)} images")
    st.markdown('---')
    st.subheader('📺 QR code for the extended display')
    ip=lan_ip(); guest_url=f'http://{ip}:8501/?mode=guest'
    st.write('Connect the laptop and guests’ phones to the same Wi-Fi network. The guest page will use this laptop as the photo-search server.')
    st.code(guest_url)
    qr=make_qr(guest_url)
    st.image(qr, caption='Scan this QR code with a phone connected to the same Wi-Fi network', width=420)
    st.markdown('**To show this QR code on your TV/second screen:** move the browser window to the extended display and press `F11` for full screen.')
    st.warning('Keep this local server running and do not close the terminal while guests are searching.')
    st.markdown('---')
    st.subheader('How to open the guest page on this laptop')
    st.markdown(f'Use [the guest page]({guest_url}) to test. If Windows Firewall asks whether Python/Streamlit may communicate on your network, allow it on **Private networks** only.')
else:
    st.title('📸 Find Your Event Photos')
    st.caption('Your selfie is processed on the event laptop. Connect to the same Wi-Fi as the photo gallery host.')
    folder=local_cfg.get('folder','')
    if not folder:
        st.error('The organizer has not configured the photo folder on the host laptop yet.'); st.stop()
    event_name=local_cfg.get('event_name','Wedding Photo Gallery')
    st.subheader(event_name)
    camera=st.camera_input('Take a selfie')
