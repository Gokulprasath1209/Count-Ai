
/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, useRef, onWillUnmount, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class AudioRecorderField extends Component {
    static template = "odoo_website_helpdesk.AudioRecorderField";

    static props = {
        ...standardFieldProps,
        id: { type: String, optional: true },
    };

    setup() {
        this.notification = useService("notification");

        this.orm = useService("orm");
        this.state = useState({
            isRecording: false,
            isPaused: false,
            recordingTime: 0,
            hasRecording: false,
            isPlaying: false,
            audioUrl: null,
            microphoneAvailable: false,
            checkingMicrophone: false,
        });

        this.mediaRecorder = null;
        this.audioChunks = [];
        this.stream = null;
        this.timerInterval = null;
        this.audioRef = useRef("audioPlayer");
        this.recordedMimeType = null;
        this.currentBlob = null;
        this.res_id = this.props.record.evalContext.id;

        console.log("============ 111111111 values ==============", this)
        // Initialize audio if value exists

        onWillUnmount(() => this.cleanup());



        onWillStart(async () => { // <-- Add 'async' here
            let values = await this.orm.call(
                "ticket.help.desk.line",
                "get_binary_field_data",
                [
                   this.res_id,
                   this.props.name,
                ]
            );
            console.log("============ values ==========", values);
            const value = this.fieldValue;
            if (values && typeof values === 'string' && values.length > 0) {
                this.state.hasRecording = true;
                this.loadAudioFromBase64(values);
            }

            this.checkMicrophoneAvailability();

        });
    }

    get fieldValue() {
        return this.props.record.data[this.props.name] || false;
    }

    updateFieldValue(value) {
        this.props.record.update({ [this.props.name]: value });
    }

    get isReadonly() {
        return this.props.readonly || false;
    }

    async loadAudioFromBase64(base64Data) {
        console.log("============= loadAudioFromBase64 ===============")
        console.log("============= base64Data ===============", base64Data)
        try {
            // Validate base64 string
            if (!base64Data || typeof base64Data !== 'string') {
                console.warn("Invalid base64 data");
                return;
            }

            // Remove any whitespace and newlines
            const cleanBase64 = base64Data.replace(/\s/g, '');

            // Check if it's valid base64
            if (!/^[A-Za-z0-9+/]*={0,2}$/.test(cleanBase64)) {
                console.warn("Invalid base64 format");
                return;
            }

            const mimeType = 'audio/webm;codecs=opus';
            const byteCharacters = atob(cleanBase64);
            const byteNumbers = new Array(byteCharacters.length);

            for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }

            const byteArray = new Uint8Array(byteNumbers);
            this.currentBlob = new Blob([byteArray], { type: mimeType });

            this.state.audioUrl = URL.createObjectURL(this.currentBlob);
            console.log("Audio loaded from database, size:", this.currentBlob.size, "bytes");

        } catch (error) {
            console.error("Error loading audio from base64:", error);
            // Don't show error to user, just log it
            this.state.hasRecording = false;
        }
    }

    async checkMicrophoneAvailability() {
        this.state.checkingMicrophone = true;

        try {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                throw new Error("MediaDevices API not supported");
            }

            const devices = await navigator.mediaDevices.enumerateDevices();
            const audioInputs = devices.filter(device => device.kind === 'audioinput');

            if (audioInputs.length === 0) {
                this.state.microphoneAvailable = false;
                this.notification.add("No microphone device found.", {
                    type: "warning",
                });
            } else {
                this.state.microphoneAvailable = true;
                console.log(`Found ${audioInputs.length} microphone(s)`);
            }
        } catch (error) {
            console.error("Error checking microphone:", error);
            this.state.microphoneAvailable = false;
        } finally {
            this.state.checkingMicrophone = false;
        }
    }

    async startRecording() {
        console.log("============= startRecording ===============", this.audioRef)
        if (!this.state.microphoneAvailable) {
            this.notification.add("No microphone found. Please connect a microphone.", {
                type: "danger"
            });
            return;
        }

        try {
            const constraints = {
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                    sampleRate: 48000,
                    channelCount: 1,
                }
            };

            this.stream = await navigator.mediaDevices.getUserMedia(constraints);

            const audioTracks = this.stream.getAudioTracks();
            if (audioTracks.length === 0) {
                throw new Error("No audio track available");
            }

            console.log("Using audio device:", audioTracks[0].label);

            this.recordedMimeType = this.getSupportedMimeType();
            console.log("Selected MIME type:", this.recordedMimeType);

            const options = {
                mimeType: this.recordedMimeType,
                audioBitsPerSecond: 128000,
            };

            this.mediaRecorder = new MediaRecorder(this.stream, options);
            this.audioChunks = [];

            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data && event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };

            this.mediaRecorder.onstop = () => {
                console.log("Recording stopped:", this.audioChunks);
                console.log("Recording stopped. Chunks:", this.audioChunks.length);

                if (this.audioChunks.length === 0) {
                    this.notification.add("No audio data captured.", { type: "warning" });
                    return;
                }

                const audioBlob = new Blob(this.audioChunks, { type: this.recordedMimeType });
                console.log("Audio blob size:", audioBlob.size, "bytes");

                if (audioBlob.size === 0) {
                    this.notification.add("Recording failed.", { type: "danger" });
                    return;
                }

                this.saveAudioToField(audioBlob);
                this.stopTimer();
            };

            this.mediaRecorder.onerror = (event) => {
                console.error("MediaRecorder error:", event.error);
                this.notification.add(`Recording error: ${event.error.name}`, { type: "danger" });
                this.stopRecording();
            };

            this.mediaRecorder.start(1000);

            this.state.isRecording = true;
            this.state.isPaused = false;
            this.state.recordingTime = 0;
            this.startTimer();

            this.notification.add("Recording started", { type: "success" });

        } catch (error) {
            console.error("Recording error:", error);

            let errorMessage = "Failed to start recording.";
            if (error.name === 'NotAllowedError') {
                errorMessage = "Microphone permission denied. Please allow access in browser settings.";
            } else if (error.name === 'NotFoundError') {
                errorMessage = "No microphone found.";
            } else if (error.name === 'NotReadableError') {
                errorMessage = "Microphone is already in use by another application.";
            }

            this.notification.add(errorMessage, { type: "danger", sticky: true });
            this.checkMicrophoneAvailability();
        }
    }

    getSupportedMimeType() {
        console.log("============= getSupportedMimeType ===============", this.audioRef)
        const types = [
            'audio/webm;codecs=opus',
            'audio/webm',
            'audio/ogg;codecs=opus',
            'audio/mp4',
        ];

        for (const type of types) {
            if (MediaRecorder.isTypeSupported(type)) {
                return type;
            }
        }
        return 'audio/webm';
    }

    pauseRecording() {
        console.log("============= pauseRecording ===============", this.audioRef)
        if (this.mediaRecorder && this.mediaRecorder.state === "recording") {
            this.mediaRecorder.pause();
            this.state.isPaused = true;
            this.stopTimer();
            this.notification.add("Recording paused", { type: "info" });
        }
    }

    resumeRecording() {
        console.log("============= resumeRecording ===============", this.audioRef)
        if (this.mediaRecorder && this.mediaRecorder.state === "paused") {
            this.mediaRecorder.resume();
            this.state.isPaused = false;
            this.startTimer();
            this.notification.add("Recording resumed", { type: "info" });
        }
    }

    stopRecording() {
        console.log("============= stopRecording ===============", this.audioRef)
        if (this.mediaRecorder && this.mediaRecorder.state !== "inactive") {
            this.mediaRecorder.stop();
            this.state.isRecording = false;
            this.state.isPaused = false;

            if (this.stream) {
                this.stream.getTracks().forEach(track => track.stop());
                this.stream = null;
            }
        }
    }

    saveAudioToField(audioBlob) {
        console.log("============= saveAudioToField ===============", this)
        this.currentBlob = audioBlob;

        const reader = new FileReader();

        reader.onloadend = () => {
            const base64Audio = reader.result.split(',')[1];
            console.log("Base64 length:", base64Audio.length);

            // Save to database
            this.updateFieldValue(base64Audio);

            // Create blob URL for immediate playback
            if (this.state.audioUrl && this.state.audioUrl.startsWith('blob:')) {
                URL.revokeObjectURL(this.state.audioUrl);
            }
            this.state.audioUrl = URL.createObjectURL(audioBlob);
            this.state.hasRecording = true;

            console.log("Recording saved successfully");
            this.notification.add("Recording saved successfully!", { type: "success" });
        };

        reader.onerror = (error) => {
            console.error("FileReader error:", error);
            this.notification.add("Failed to save recording", { type: "danger" });
        };

        reader.readAsDataURL(audioBlob);
    }

    async playAudio() {
        console.log("============= audioChunks ===============", this)
        console.log("============= audioUrl ===============", this.audioUrl)
        console.log("============= playAudio ===============", this.audioRef)
        const audio = this.audioRef.el;
        if (!audio) {
            console.error("Audio element not found");
            return;
        }

        console.log("Playing audio...", audio);

        try {
            audio.volume = 1.0;
            audio.muted = false;

            audio.load();
            await audio.play();

            this.state.isPlaying = true;
            console.log("Playback started");

            audio.onended = () => {
                this.state.isPlaying = false;
                console.log("Playback ended");
            };

        } catch (error) {
            console.error("Playback error:", error);
            this.notification.add(`Failed to play audio: ${error.message}`, {
                type: "danger",
            });
        }
    }

    pauseAudio() {
    console.log("========= pauseAudio ===========", this.audioRef)
    console.log("========= pauseAudio ===========", this.audioRef.el)
        const audio = this.audioRef.el;
        if (audio) {
            audio.pause();
            this.state.isPlaying = false;
        }
    }

    deleteRecording() {

    console.log("========= deleteRecording ===========", this.state.audioUr)
        if (this.state.audioUrl && this.state.audioUrl.startsWith('blob:')) {
            URL.revokeObjectURL(this.state.audioUrl);
        }

        this.updateFieldValue(false);
        this.state.hasRecording = false;
        this.state.audioUrl = null;
        this.state.recordingTime = 0;
        this.recordedMimeType = null;
        this.currentBlob = null;

        this.notification.add("Recording deleted", { type: "info" });
    }

    async downloadRecording() {
    console.log("========= downloadRecording ===========", this.currentBlob)
        if (this.currentBlob) {
            try {
                const url = URL.createObjectURL(this.currentBlob);
                const link = document.createElement("a");
                link.href = url;

                let extension = 'webm';
                if (this.recordedMimeType?.includes('mp4')) extension = 'mp4';
                else if (this.recordedMimeType?.includes('ogg')) extension = 'ogg';

                link.download = `recording_${Date.now()}.${extension}`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                URL.revokeObjectURL(url);

                this.notification.add("Recording downloaded", { type: "success" });
            } catch (error) {
                console.error("Download error:", error);
                this.notification.add("Download failed", { type: "danger" });
            }
        }
    }

    startTimer() {
        this.timerInterval = setInterval(() => {
            this.state.recordingTime++;
        }, 1000);
    }

    stopTimer() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
    }

    get formattedTime() {
        const minutes = Math.floor(this.state.recordingTime / 60);
        const seconds = this.state.recordingTime % 60;
        return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
    }

    cleanup() {
    console.log("============ cleanup ===========", this)
        this.stopTimer();
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
        }
        if (this.state.audioUrl && this.state.audioUrl.startsWith('blob:')) {
            URL.revokeObjectURL(this.state.audioUrl);
        }
    }
}

export const audioRecorderField = {
    component: AudioRecorderField,
    supportedTypes: ["binary"],
};

registry.category("fields").add("audio_recorder", audioRecorderField);