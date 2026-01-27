/** @odoo-module **/

import { Component, useState, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class InlineVideoRecorder extends Component {
    static template = "odoo_website_helpdesk.InlineVideoRecorder";

    setup() {
        // Reactive state
        this.state = useState({
            recording: false,
            videoURL: null,
            timer: 0,
        });

        // Internal properties
        this.mediaRecorder = null;
        this.videoChunks = [];
        this.timerInterval = null;
        this.stream = null;

        // Cleanup on component destruction
        onWillUnmount(() => {
            if (this.timerInterval) clearInterval(this.timerInterval);
            if (this.stream) this.stream.getTracks().forEach(track => track.stop());
        });
    }

    // Toggle recording
    async toggleRecording() {
        if (this.state.recording) {
            this.stopRecording();
        } else {
            await this.startRecording();
        }
    }

    // Start recording
    async startRecording() {
        try {
            // Request camera + microphone
            this.stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });

            // Show live preview
            const videoPreview = this.el.querySelector("#liveVideoPreview");
            if (videoPreview) {
                videoPreview.srcObject = this.stream;
                videoPreview.play();
            }

            // Setup MediaRecorder
            this.mediaRecorder = new MediaRecorder(this.stream, { mimeType: "video/webm" });
            this.videoChunks = [];

            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.videoChunks.push(event.data);
                }
            };

            this.mediaRecorder.onstop = () => {
                const videoBlob = new Blob(this.videoChunks, { type: "video/webm" });
                this.state.videoURL = URL.createObjectURL(videoBlob);

                // Convert blob to base64
                const reader = new FileReader();
                reader.readAsDataURL(videoBlob);
                reader.onloadend = () => {
                    const base64data = reader.result.split(",")[1];
                    this.saveToOdoo(base64data);
                };

                // Stop camera tracks
                if (this.stream) {
                    this.stream.getTracks().forEach(track => track.stop());
                }
            };

            this.mediaRecorder.start();
            this.state.recording = true;
            this.state.timer = 0;

            // Timer increment
            this.timerInterval = setInterval(() => this.state.timer++, 1000);
        } catch (error) {
            console.error("Camera or microphone access denied:", error);
            alert("Please allow camera and microphone access.");
        }
    }

    // Stop recording
    stopRecording() {
        if (this.mediaRecorder && this.mediaRecorder.state !== "inactive") {
            this.mediaRecorder.stop();
        }
        this.state.recording = false;
        clearInterval(this.timerInterval);
    }

    // Save video to Odoo record
    async saveToOdoo(base64data) {
        if (!this.props.recordId) {
            console.error("Missing recordId for RPC");
            return;
        }

        try {
            await this.env.services.rpc({
                model: "helpdesk.ticket", // Correct model
                method: "write",
                args: [[this.props.recordId], {
                    video_recording: base64data,
                    video_filename: "video_recording.webm",
                }],
            });

            this.displayNotification({
                type: "success",
                title: "Video Recording Saved",
            });
        } catch (error) {
            console.error("Error saving video to Odoo:", error);
            this.displayNotification({
                type: "danger",
                title: "Failed to save video",
                message: error.message,
            });
        }
    }
}

// Register component
registry.category("components").add(
    "odoo_website_helpdesk.InlineVideoRecorder",
    InlineVideoRecorder
);
