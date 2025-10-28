///** @odoo-module **/
//
//import { registry } from "@web/core/registry";
//import { Component, useState, useRef, onWillUnmount } from "@odoo/owl";
//import { useService } from "@web/core/utils/hooks";
//
//export class AudioRecorderField extends Component {
//    static template = "odoo_website_helpdesk.AudioRecorderField";
//
//    static props = {
//        readonly: { type: Boolean, optional: true },
//        record: { type: Object, optional: true },
//        name: { type: String, optional: true },
//        value: { type: [String, Boolean], optional: true },
//        update: { type: Function, optional: true },
//        type: { type: String, optional: true },
//    };
//
//    setup() {
//        console.log("AudioRecorderField setup called");
//        console.log("Props:", this.props);
//
//        this.notification = useService("notification");
//
//        this.state = useState({
//            isRecording: false,
//            isPaused: false,
//            recordingTime: 0,
//            hasRecording: false,
//            isPlaying: false,
//            audioUrl: null,
//        });
//
//        this.mediaRecorder = null;
//        this.audioChunks = [];
//        this.stream = null;
//        this.timerInterval = null;
//        this.audioRef = useRef("audioPlayer");
//
//        // Initialize audio if value exists
//        const value = this.fieldValue;
//        if (value) {
//            this.state.hasRecording = true;
//            this.state.audioUrl = `data:audio/webm;base64,${value}`;
//        }
//
//        onWillUnmount(() => this.cleanup());
//    }
//
//    get fieldValue() {
//        // Handle both direct value prop and record data access
//        if (this.props.value !== undefined) {
//            return this.props.value;
//        }
//        if (this.props.record && this.props.name) {
//            return this.props.record.data[this.props.name];
//        }
//        return false;
//    }
//
//    updateFieldValue(value) {
//        // Handle both direct update function and record update
//        if (this.props.update) {
//            this.props.update(value);
//        } else if (this.props.record && this.props.name) {
//            this.props.record.update({ [this.props.name]: value });
//        }
//    }
//
//    get isReadonly() {
//        return this.props.readonly || false;
//    }
//
//    async startRecording() {
//        try {
//            this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
//
//            const mimeType = this.getSupportedMimeType();
//            this.mediaRecorder = new MediaRecorder(this.stream, { mimeType });
//            this.audioChunks = [];
//
//            this.mediaRecorder.ondataavailable = (event) => {
//                if (event.data.size > 0) {
//                    this.audioChunks.push(event.data);
//                }
//            };
//
//            this.mediaRecorder.onstop = () => {
//                const audioBlob = new Blob(this.audioChunks, { type: mimeType });
//                this.saveAudioToField(audioBlob);
//                this.stopTimer();
//            };
//
//            this.mediaRecorder.start();
//            this.state.isRecording = true;
//            this.state.isPaused = false;
//            this.state.recordingTime = 0;
//            this.startTimer();
//
//            this.notification.add("Recording started", { type: "info" });
//        } catch (error) {
//            console.error("Microphone error:", error);
//            this.notification.add("Microphone access denied. Please allow permissions.", {
//                type: "danger"
//            });
//        }
//    }
//
//    getSupportedMimeType() {
//        const types = [
//            'audio/webm;codecs=opus',
//            'audio/webm',
//            'audio/ogg;codecs=opus',
//            'audio/mp4'
//        ];
//        for (const type of types) {
//            if (MediaRecorder.isTypeSupported(type)) {
//                return type;
//            }
//        }
//        return 'audio/webm';
//    }
//
//    pauseRecording() {
//        if (this.mediaRecorder && this.mediaRecorder.state === "recording") {
//            this.mediaRecorder.pause();
//            this.state.isPaused = true;
//            this.stopTimer();
//            this.notification.add("Recording paused", { type: "info" });
//        }
//    }
//
//    resumeRecording() {
//        if (this.mediaRecorder && this.mediaRecorder.state === "paused") {
//            this.mediaRecorder.resume();
//            this.state.isPaused = false;
//            this.startTimer();
//            this.notification.add("Recording resumed", { type: "info" });
//        }
//    }
//
//    stopRecording() {
//        if (this.mediaRecorder && this.mediaRecorder.state !== "inactive") {
//            this.mediaRecorder.stop();
//            this.state.isRecording = false;
//            this.state.isPaused = false;
//
//            if (this.stream) {
//                this.stream.getTracks().forEach(track => track.stop());
//            }
//
//            this.notification.add("Recording saved", { type: "success" });
//        }
//    }
//
//    saveAudioToField(audioBlob) {
//        const reader = new FileReader();
//        reader.onloadend = () => {
//            const base64Audio = reader.result.split(',')[1];
//            this.updateFieldValue(base64Audio);
//
//            this.state.hasRecording = true;
//            this.state.audioUrl = reader.result;
//        };
//        reader.readAsDataURL(audioBlob);
//    }
//
//    playAudio() {
//        const audio = this.audioRef.el;
//        if (audio) {
//            audio.play();
//            this.state.isPlaying = true;
//            audio.onended = () => {
//                this.state.isPlaying = false;
//            };
//        }
//    }
//
//    pauseAudio() {
//        const audio = this.audioRef.el;
//        if (audio) {
//            audio.pause();
//            this.state.isPlaying = false;
//        }
//    }
//
//    deleteRecording() {
//        this.updateFieldValue(false);
//        this.state.hasRecording = false;
//        this.state.audioUrl = null;
//        this.state.recordingTime = 0;
//        this.notification.add("Recording deleted", { type: "info" });
//    }
//
//    downloadRecording() {
//        if (this.state.audioUrl) {
//            const link = document.createElement("a");
//            link.href = this.state.audioUrl;
//            link.download = `recording_${Date.now()}.webm`;
//            document.body.appendChild(link);
//            link.click();
//            document.body.removeChild(link);
//        }
//    }
//
//    startTimer() {
//        this.timerInterval = setInterval(() => {
//            this.state.recordingTime++;
//        }, 1000);
//    }
//
//    stopTimer() {
//        if (this.timerInterval) {
//            clearInterval(this.timerInterval);
//            this.timerInterval = null;
//        }
//    }
//
//    get formattedTime() {
//        const minutes = Math.floor(this.state.recordingTime / 60);
//        const seconds = this.state.recordingTime % 60;
//        return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
//    }
//
//    cleanup() {
//        this.stopTimer();
//        if (this.stream) {
//            this.stream.getTracks().forEach(track => track.stop());
//        }
//        if (this.state.audioUrl && this.state.audioUrl.startsWith('blob:')) {
//            URL.revokeObjectURL(this.state.audioUrl);
//        }
//    }
//}
//
//export const audioRecorderField = {
//    component: AudioRecorderField,
//    supportedTypes: ["binary"],
//    extractProps: ({ attrs, field }) => {
//        return {
//            readonly: attrs.readonly,
//            type: field.type,
//        };
//    },
//};
//
//registry.category("fields").add("audio_recorder", audioRecorderField);

/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, useRef, onWillUnmount } from "@odoo/owl";
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

        // Initialize audio if value exists
        const value = this.fieldValue;
        if (value && typeof value === 'string' && value.length > 0) {
            this.state.hasRecording = true;
            this.loadAudioFromBase64(value);
        }

        this.checkMicrophoneAvailability();

        onWillUnmount(() => this.cleanup());
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
        if (this.mediaRecorder && this.mediaRecorder.state === "recording") {
            this.mediaRecorder.pause();
            this.state.isPaused = true;
            this.stopTimer();
            this.notification.add("Recording paused", { type: "info" });
        }
    }

    resumeRecording() {
        if (this.mediaRecorder && this.mediaRecorder.state === "paused") {
            this.mediaRecorder.resume();
            this.state.isPaused = false;
            this.startTimer();
            this.notification.add("Recording resumed", { type: "info" });
        }
    }

    stopRecording() {
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
        const audio = this.audioRef.el;
        if (!audio) {
            console.error("Audio element not found");
            return;
        }

        console.log("Playing audio...");

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
        const audio = this.audioRef.el;
        if (audio) {
            audio.pause();
            this.state.isPlaying = false;
        }
    }

    deleteRecording() {
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