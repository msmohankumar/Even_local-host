    folder=st.text_input('Photo folder path', value=st.session_state.get('local_folder', ''), placeholder=r'E:\Wedding Photos or C:\Users\YourName\Pictures\Wedding')
    st.session_state['local_folder']=folder
    event_name=st.text_input('Event name', value=st.session_state.get('local_event_name','Wedding Photo Gallery'))
    if st.button('Scan photo folder', type='primary'):
        if not folder.strip(): st.error('Enter a folder path first.')
        else:
            with st.spinner('Scanning folder and subfolders...'):
                try:
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
    uploads=st.file_uploader('Or upload selfie image(s)', type=['jpg','jpeg','png','webp'], accept_multiple_files=True)
    selfies=[]
    if camera: selfies.append({'name':'Camera selfie','bytes':camera.getvalue()})
    if uploads:
        selfies.extend({'name':f.name,'bytes':f.getvalue()} for f in uploads)
    threshold=st.slider('Matching sensitivity',0.20,0.70,0.40,0.01, help='Lower is stricter; higher may increase false matches.')
    if selfies and st.button('🔎 Find My Photos', type='primary', use_container_width=True):
        try:
            with st.spinner('Loading local photos...'):
                images=load_local_gallery(folder)
            if not images: st.error('No supported photos found in the configured folder.')
            else:
                merged={}; all_errors=[]; progress=st.progress(0)
                for si,selfie in enumerate(selfies):
                    try:
                        matches,errs=find_matches(selfie['bytes'],images,threshold); all_errors.extend(errs)
                        for m in matches:
                            if m['name'] not in merged or m['distance']<merged[m['name']]['distance']: merged[m['name']]=m
                    except Exception as e: all_errors.append(f"{selfie['name']}: {e}")
                    progress.progress((si+1)/len(selfies))
                progress.empty(); results=sorted(merged.values(),key=lambda m:m['distance'])
                st.session_state['local_matches']=results; st.session_state['local_errors']=all_errors; st.session_state['local_total']=len(images)
        except Exception as e: st.error(f'Gallery search failed: {e}')
    if 'local_matches' in st.session_state:
        matches=st.session_state['local_matches']; errors=st.session_state.get('local_errors',[])
        st.markdown('---'); st.subheader('🎉 Search Results'); st.write(f"Gallery images scanned: {st.session_state.get('local_total',0)} | Matches: {len(matches)}")
        if not matches: st.warning('No matching photos found. Try another selfie or sensitivity setting.')
        else:
            cols=st.columns(3)
            for i,m in enumerate(matches):
                with cols[i%3]:
                    st.image(m['preview'], use_container_width=True); st.caption(m['name']); st.caption(f"Distance: {m['distance']:.4f}")
                    st.download_button('⬇️ Download photo',m['original'],file_name=Path(m['name']).name,mime='image/jpeg',key=f'local_download_{i}',use_container_width=True)
            if len(matches)>1:
                buf=io.BytesIO()
                with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
                    for m in matches: z.writestr(m['name'],m['original'])
                st.download_button('📦 Download all matching photos',buf.getvalue(),file_name='my_event_photos.zip',mime='application/zip',use_container_width=True)
        if errors:
            with st.expander('Processing notes/errors'):
                for e in errors[:30]: st.write(e)
