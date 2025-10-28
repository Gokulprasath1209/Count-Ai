/** @odoo-module **/

import { Component, useState, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class HelpdeskAttachmentManager extends Component {
    static template = "odoo_website_helpdesk.HelpdeskAttachmentManager";

    setup() {
        this.rpc = useService("rpc");
        this.notification = useService("notification");

        // Reactive state
        this.state = useState({
            recording: false,
            audioURL: null,
            timer: 0,
        });

        this.mediaRecorder = null;
        this.audioChunks = [];
        this.timerInterval = null;

        // Cleanup when the component unmounts
        onWillUnmount(() => {
            if (this.timerInterval) clearInterval(this.timerInterval);
            if (this.stream) this.stream.getTracks().forEach((track) => track.stop());
        });
    }

    /** 🎤 Toggle voice recording */
    async toggleRecording() {
        if (this.state.recording) {
            this.stopRecording();
        } else {
            await this.startRecording();
        }
    }

    /** ▶️ Start recording */
    async startRecording() {
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.mediaRecorder = new MediaRecorder(this.stream);
            this.audioChunks = [];

            this.mediaRecorder.ondataavailable = (event) => {
                this.audioChunks.push(event.data);
            };

            this.mediaRecorder.onstop = () => {
                const audioBlob = new Blob(this.audioChunks, { type: "audio/wav" });
                const audioURL = URL.createObjectURL(audioBlob);
                this.state.audioURL = audioURL;
                this.saveVoiceRecording(audioBlob);
            };

            this.mediaRecorder.start();
            this.state.recording = true;
            this.state.timer = 0;

            this.timerInterval = setInterval(() => this.state.timer++, 1000);
        } catch (error) {
            console.error("Microphone access denied:", error);
            this.notification.add("Microphone access denied.", { type: "danger" });
        }
    }

    /** ⏹ Stop recording */
    stopRecording() {
        if (this.mediaRecorder && this.mediaRecorder.state !== "inactive") {
            this.mediaRecorder.stop();
        }
        this.state.recording = false;
        clearInterval(this.timerInterval);
        if (this.stream) this.stream.getTracks().forEach((track) => track.stop());
    }

    /** 💾 Save recorded voice as attachment */
    async saveVoiceRecording(blob) {
        const reader = new FileReader();
        reader.readAsDataURL(blob);
        reader.onloadend = async () => {
            const base64data = reader.result.split(",")[1];
            const filename = `voice_${Date.now()}.wav`;

            await this.rpc("/web/dataset/call_kw/helpdesk.attachment/create", {
                model: "helpdesk.attachment",
                method: "create",
                args: [
                    {
                        ticket_id: this.props.recordId,
                        attachment_type: "voice",
                        name: filename,
                        file_data: base64data,
                    },
                ],
            });

            this.notification.add("🎧 Voice Recording Saved!", { type: "success" });
        };
    }

    /** 📸 Upload multiple images */
    async uploadImages(event) {
        const files = event.target.files;
        for (let file of files) {
            const reader = new FileReader();
            reader.readAsDataURL(file);
            reader.onloadend = async () => {
                const base64data = reader.result.split(",")[1];
                await this.rpc("/web/dataset/call_kw/helpdesk.attachment/create", {
                    model: "helpdesk.attachment",
                    method: "create",
                    args: [
                        {
                            ticket_id: this.props.recordId,
                            attachment_type: "image",
                            name: file.name,
                            file_data: base64data,
                        },
                    ],
                });

                this.notification.add(`${file.name} uploaded`, { type: "success" });
            };
        }
    }
}

// ✅ Register the component once
registry.category("components").add(
    "odoo_website_helpdesk.HelpdeskAttachmentManager",
    HelpdeskAttachmentManager
);
