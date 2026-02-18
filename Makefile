.PHONY: update-checksums

# Download models and update SHA256 checksums in both Dockerfiles
update-checksums:
	@echo "Computing model checksums..."
	@# Shape predictor (download compressed, hash uncompressed)
	@wget -q http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2 -O /tmp/gsd_sp.bz2
	@bunzip2 -f /tmp/gsd_sp.bz2
	@SP_HASH=$$(sha256sum /tmp/gsd_sp | awk '{print $$1}') && \
		echo "  shape_predictor: $$SP_HASH" && \
		sed -i "s/^ARG SHAPE_PREDICTOR_SHA256=.*/ARG SHAPE_PREDICTOR_SHA256=$$SP_HASH/" \
			docker/Dockerfile.cpu docker/Dockerfile.gpu
	@rm -f /tmp/gsd_sp
	@# CodeFormer
	@wget -q https://github.com/sczhou/CodeFormer/releases/download/v0.1.0/codeformer.pth -O /tmp/gsd_cf.pth
	@CF_HASH=$$(sha256sum /tmp/gsd_cf.pth | awk '{print $$1}') && \
		echo "  codeformer: $$CF_HASH" && \
		sed -i "s/^ARG CODEFORMER_SHA256=.*/ARG CODEFORMER_SHA256=$$CF_HASH/" \
			docker/Dockerfile.cpu docker/Dockerfile.gpu
	@rm -f /tmp/gsd_cf.pth
	@# u2net_human_seg (requires Python with rembg)
	@python -c "from rembg import new_session; new_session('u2net_human_seg')" 2>/dev/null
	@U2_HASH=$$(sha256sum $$HOME/.u2net/u2net_human_seg.onnx | awk '{print $$1}') && \
		echo "  u2net_human_seg: $$U2_HASH" && \
		sed -i "s/^ARG U2NET_SHA256=.*/ARG U2NET_SHA256=$$U2_HASH/" \
			docker/Dockerfile.cpu docker/Dockerfile.gpu
	@echo "Checksums updated in docker/Dockerfile.cpu and docker/Dockerfile.gpu"
