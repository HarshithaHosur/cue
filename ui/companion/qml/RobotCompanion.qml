// ============================================================
//  KAWAII AI ROBOT COMPANION — Super Cute Expressive QML Component
//  60fps fluid animated desktop companion with charming personality
// ============================================================

import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: root
    width: 220
    height: 260

    // ── Properties exposed to Python ──
    property string state: "idle"        // idle, listening, thinking, executing, success, error
    property string companionState: "idle"
    property string bubbleText: ""
    property string speechText: ""
    property bool   companionVisible: true
    property real   companionScale: 1.0

    // ── Internal animation state ──
    property real breathPhase: 0.0
    property real blinkPhase: 0.0
    property bool isBlinking: false
    property real eyeLookX: 0.0
    property real eyeLookY: 0.0
    property real headTilt: 0.0
    property real bodyBounce: 0.0
    property real glowPulse: 0.0
    property real earWiggle: 0.0

    visible: companionVisible
    opacity: companionVisible ? 1.0 : 0.0
    scale: companionScale

    Behavior on opacity { NumberAnimation { duration: 300; easing.type: Easing.InOutQuad } }
    Behavior on scale   { NumberAnimation { duration: 350; easing.type: Easing.OutBack } }

    // ============================================================
    //  CONTINUOUS IDLE ANIMATIONS
    // ============================================================
    NumberAnimation on breathPhase {
        from: 0; to: 2 * Math.PI
        duration: 3200
        loops: Animation.Infinite
        running: true
    }

    NumberAnimation on glowPulse {
        from: 0; to: 2 * Math.PI
        duration: 2200
        loops: Animation.Infinite
        running: true
    }

    // Natural blinking
    Timer {
        id: blinkTimer
        interval: 2200 + Math.random() * 3000
        repeat: true
        running: true
        onTriggered: {
            isBlinking = true
            blinkResetTimer.start()
            interval = 2200 + Math.random() * 3000
        }
    }

    Timer {
        id: blinkResetTimer
        interval: 160
        repeat: false
        onTriggered: isBlinking = false
    }

    // Gentle curious gaze shift
    Timer {
        id: lookTimer
        interval: 3500 + Math.random() * 4000
        repeat: true
        running: true
        onTriggered: {
            eyeLookX = (Math.random() - 0.5) * 6
            eyeLookY = (Math.random() - 0.5) * 3
            interval = 3500 + Math.random() * 4000
        }
    }
    Behavior on eyeLookX { NumberAnimation { duration: 500; easing.type: Easing.InOutQuad } }
    Behavior on eyeLookY { NumberAnimation { duration: 500; easing.type: Easing.InOutQuad } }

    // Cute head tilt
    Timer {
        id: headTiltTimer
        interval: 3000 + Math.random() * 4000
        repeat: true
        running: true
        onTriggered: {
            headTilt = (Math.random() - 0.5) * 8
            earWiggle = (Math.random() - 0.5) * 10
            interval = 3000 + Math.random() * 4000
        }
    }
    Behavior on headTilt { NumberAnimation { duration: 700; easing.type: Easing.InOutSine } }
    Behavior on earWiggle { NumberAnimation { duration: 400; easing.type: Easing.OutBack } }

    // Happy bounce on state change
    SequentialAnimation {
        id: bounceAnim
        NumberAnimation { target: root; property: "bodyBounce"; to: -14; duration: 130; easing.type: Easing.OutQuad }
        NumberAnimation { target: root; property: "bodyBounce"; to: 6; duration: 160; easing.type: Easing.InOutQuad }
        NumberAnimation { target: root; property: "bodyBounce"; to: 0; duration: 250; easing.type: Easing.OutBounce }
    }

    onStateChanged: bounceAnim.start()
    onCompanionStateChanged: bounceAnim.start()

    // Dynamic accent color based on mood
    function getAccentColor() {
        var s = (root.state || root.companionState).toLowerCase()
        if (s.indexOf("think") !== -1 || s.indexOf("cursor") !== -1) return "#c084fc"   // Lavender purple
        if (s.indexOf("listen") !== -1) return "#38bdf8"                              // Bright sky cyan
        if (s.indexOf("success") !== -1) return "#34d399"                             // Emerald green
        if (s.indexOf("error") !== -1 || s.indexOf("lost") !== -1) return "#f87171"   // Soft alert coral
        return "#38bdf8"                                                              // Happy cyan
    }

    // ============================================================
    //  ROBOT CHARACTER
    // ============================================================
    Item {
        id: robot
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 18
        width: 140
        height: 160
        rotation: headTilt
        y: Math.sin(breathPhase) * 4 + bodyBounce

        Behavior on rotation { NumberAnimation { duration: 450; easing.type: Easing.InOutQuad } }

        // ── Soft Glowing Shadow ──
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: -6
            width: 90 + Math.sin(breathPhase) * 6
            height: 18
            radius: 9
            color: {
                var alpha = 0.22 + Math.sin(glowPulse) * 0.08
                var col = Qt.color(getAccentColor())
                return Qt.rgba(col.r, col.g, col.b, alpha)
            }
        }

        // ── Cute Antenna with Heart/Orb ──
        Item {
            id: antenna
            anchors.horizontalCenter: headShell.horizontalCenter
            anchors.bottom: headShell.top
            anchors.bottomMargin: -2
            width: 24
            height: 28
            rotation: Math.sin(breathPhase * 1.5) * 6 + earWiggle

            Behavior on rotation { NumberAnimation { duration: 300 } }

            // Stem
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                width: 3.5
                height: 18
                radius: 2
                color: "#475569"
            }

            // Glowing Star / Heart Orb on top
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                width: 14 + Math.sin(glowPulse * 2) * 2
                height: width
                radius: width / 2
                color: getAccentColor()
                border.color: "#ffffff"
                border.width: 1.5

                // Inner core shine
                Rectangle {
                    anchors.centerIn: parent
                    width: parent.width * 0.5
                    height: width
                    radius: width / 2
                    color: "#ffffff"
                    opacity: 0.85
                }
            }
        }

        // ── Cute Cat-like Ears / Horns ──
        Rectangle {
            anchors.right: headShell.left
            anchors.rightMargin: -12
            anchors.top: headShell.top
            anchors.topMargin: 4
            width: 16
            height: 18
            radius: 8
            rotation: -25 + Math.sin(breathPhase) * 4
            color: "#1e293b"
            border.color: getAccentColor()
            border.width: 1.5

            Rectangle {
                anchors.centerIn: parent
                width: 7
                height: 8
                radius: 4
                color: "#ff80bf"
                opacity: 0.8
            }
        }

        Rectangle {
            anchors.left: headShell.right
            anchors.leftMargin: -12
            anchors.top: headShell.top
            anchors.topMargin: 4
            width: 16
            height: 18
            radius: 8
            rotation: 25 - Math.sin(breathPhase) * 4
            color: "#1e293b"
            border.color: getAccentColor()
            border.width: 1.5

            Rectangle {
                anchors.centerIn: parent
                width: 7
                height: 8
                radius: 4
                color: "#ff80bf"
                opacity: 0.8
            }
        }

        // ── Body Shell ──
        Rectangle {
            id: bodyShell
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 8
            width: 86
            height: 56
            radius: 22
            color: "#0f172a"
            border.color: getAccentColor()
            border.width: 2

            Behavior on border.color { ColorAnimation { duration: 350 } }

            // Belly plate
            Rectangle {
                anchors.centerIn: parent
                width: 54
                height: 34
                radius: 14
                color: "#1e293b"

                // Belly Core Glow
                Rectangle {
                    anchors.centerIn: parent
                    width: 14
                    height: 14
                    radius: 7
                    color: getAccentColor()

                    Rectangle {
                        anchors.centerIn: parent
                        width: 6
                        height: 6
                        radius: 3
                        color: "#ffffff"
                    }
                }
            }
        }

        // ── Little Floating Hands / Paws ──
        Rectangle {
            id: leftHand
            anchors.right: bodyShell.left
            anchors.rightMargin: 2
            y: bodyShell.y + 12 + Math.sin(breathPhase + 1.2) * 5
            width: 14
            height: 16
            radius: 7
            color: "#1e293b"
            border.color: getAccentColor()
            border.width: 1.5
            rotation: -10 + Math.sin(breathPhase * 2) * 6
        }

        Rectangle {
            id: rightHand
            anchors.left: bodyShell.right
            anchors.leftMargin: 2
            y: bodyShell.y + 12 + Math.sin(breathPhase + 2.5) * 5
            width: 14
            height: 16
            radius: 7
            color: "#1e293b"
            border.color: getAccentColor()
            border.width: 1.5
            rotation: 10 - Math.sin(breathPhase * 2) * 6
        }

        // ── Head Shell (Rounded Cute Face) ──
        Rectangle {
            id: headShell
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: bodyShell.top
            anchors.bottomMargin: -10
            width: 104
            height: 80
            radius: 34
            color: "#0f172a"
            border.color: getAccentColor()
            border.width: 2

            Behavior on border.color { ColorAnimation { duration: 350 } }

            // Visor Screen
            Rectangle {
                id: visor
                anchors.centerIn: parent
                width: 90
                height: 66
                radius: 26
                color: "#090d16"

                // ── Kawaii Eyes ──
                // Left Eye
                Item {
                    id: leftEyeContainer
                    x: 14 + eyeLookX
                    y: 14 + eyeLookY
                    width: 26
                    height: isBlinking ? 4 : 28

                    Behavior on height { NumberAnimation { duration: 70 } }

                    Rectangle {
                        anchors.fill: parent
                        radius: isBlinking ? 2 : 13
                        color: getAccentColor()

                        // Dark pupil center
                        Rectangle {
                            anchors.centerIn: parent
                            width: isBlinking ? parent.width : 16
                            height: isBlinking ? 3 : 18
                            radius: 8
                            color: "#030712"
                            visible: !isBlinking

                            // Cute Sparkle 1 (Large shiny catchlight)
                            Rectangle {
                                x: 3
                                y: 3
                                width: 6
                                height: 6
                                radius: 3
                                color: "#ffffff"
                            }

                            // Cute Sparkle 2 (Small twinkle catchlight)
                            Rectangle {
                                x: 10
                                y: 11
                                width: 3
                                height: 3
                                radius: 1.5
                                color: "#ffffff"
                                opacity: 0.9
                            }
                        }
                    }
                }

                // Right Eye
                Item {
                    id: rightEyeContainer
                    x: 50 + eyeLookX
                    y: 14 + eyeLookY
                    width: 26
                    height: isBlinking ? 4 : 28

                    Behavior on height { NumberAnimation { duration: 70 } }

                    Rectangle {
                        anchors.fill: parent
                        radius: isBlinking ? 2 : 13
                        color: getAccentColor()

                        Rectangle {
                            anchors.centerIn: parent
                            width: isBlinking ? parent.width : 16
                            height: isBlinking ? 3 : 18
                            radius: 8
                            color: "#030712"
                            visible: !isBlinking

                            // Cute Sparkle 1 (Large catchlight)
                            Rectangle {
                                x: 3
                                y: 3
                                width: 6
                                height: 6
                                radius: 3
                                color: "#ffffff"
                            }

                            // Cute Sparkle 2 (Small twinkle)
                            Rectangle {
                                x: 10
                                y: 11
                                width: 3
                                height: 3
                                radius: 1.5
                                color: "#ffffff"
                                opacity: 0.9
                            }
                        }
                    }
                }

                // ── Glowing Rosy Blush Cheeks ──
                Rectangle {
                    x: 6
                    y: 38
                    width: 15
                    height: 9
                    radius: 4.5
                    color: "#ff66aa"
                    opacity: 0.75 + Math.sin(glowPulse) * 0.2
                }

                Rectangle {
                    x: 69
                    y: 38
                    width: 15
                    height: 9
                    radius: 4.5
                    color: "#ff66aa"
                    opacity: 0.75 + Math.sin(glowPulse) * 0.2
                }

                // ── Adorable Happy Smiling Mouth ──
                Canvas {
                    id: cuteMouth
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: 43
                    width: 24
                    height: 14
                    property string mood: root.state || root.companionState
                    property color mouthColor: Qt.color(getAccentColor())

                    onMoodChanged: requestPaint()
                    onMouthColorChanged: requestPaint()

                    onPaint: {
                        var ctx = getContext("2d");
                        ctx.clearRect(0, 0, width, height);
                        var s = mood.toLowerCase();

                        if (s.indexOf("listen") !== -1) {
                            // Curious open O mouth
                            ctx.beginPath();
                            ctx.ellipse(8, 2, 8, 8);
                            ctx.fillStyle = "#ff5376";
                            ctx.fill();
                            ctx.lineWidth = 1.5;
                            ctx.strokeStyle = "#ffffff";
                            ctx.stroke();
                        } else if (s.indexOf("error") !== -1) {
                            // Surprised / cute worried round mouth
                            ctx.beginPath();
                            ctx.arc(12, 10, 5, 1.1 * Math.PI, 1.9 * Math.PI, false);
                            ctx.lineWidth = 2.5;
                            ctx.strokeStyle = "#f87171";
                            ctx.lineCap = "round";
                            ctx.stroke();
                        } else {
                            // Big happy kawaii smile with tongue!
                            ctx.beginPath();
                            ctx.moveTo(3, 3);
                            ctx.quadraticCurveTo(12, 14, 21, 3);
                            ctx.closePath();
                            ctx.fillStyle = "#1e1e2e";
                            ctx.fill();
                            ctx.lineWidth = 2;
                            ctx.strokeStyle = mouthColor;
                            ctx.lineCap = "round";
                            ctx.stroke();

                            // Cute little pink tongue
                            ctx.beginPath();
                            ctx.arc(12, 8, 4.5, 0, Math.PI, false);
                            ctx.fillStyle = "#ff6b9d";
                            ctx.fill();
                        }
                    }
                }
            }
        }
    }

    // ============================================================
    //  KAWAII SPEECH BUBBLE
    // ============================================================
    Rectangle {
        id: speechBubble
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: robot.top
        anchors.bottomMargin: 8
        width: Math.min(Math.max(bubbleLabel.implicitWidth + 24, 70), 200)
        height: Math.max(bubbleLabel.implicitHeight + 14, 30)
        radius: 12
        color: "#1e1b4b"
        border.color: getAccentColor()
        border.width: 1.5

        property string currentText: bubbleText.length > 0 ? bubbleText : speechText
        visible: currentText.length > 0
        opacity: currentText.length > 0 ? 1.0 : 0.0

        Behavior on opacity { NumberAnimation { duration: 250 } }
        Behavior on width   { NumberAnimation { duration: 200; easing.type: Easing.OutBack } }

        Text {
            id: bubbleLabel
            anchors.centerIn: parent
            text: speechBubble.currentText
            color: "#f1f5f9"
            font.pixelSize: 11
            font.weight: Font.DemiBold
            font.family: "Segoe UI"
            wrapMode: Text.Wrap
            horizontalAlignment: Text.AlignHCenter
            width: parent.width - 16
        }

        // Triangle pointer
        Canvas {
            anchors.top: parent.bottom
            anchors.topMargin: -1
            anchors.horizontalCenter: parent.horizontalCenter
            width: 10
            height: 6
            onPaint: {
                var ctx = getContext("2d");
                ctx.fillStyle = "#1e1b4b";
                ctx.beginPath();
                ctx.moveTo(0, 0);
                ctx.lineTo(10, 0);
                ctx.lineTo(5, 6);
                ctx.closePath();
                ctx.fill();
            }
        }
    }

    // Speech bubble auto-hide timer
    Timer {
        id: bubbleHideTimer
        interval: 4500
        repeat: false
        onTriggered: {
            bubbleText = ""
            speechText = ""
        }
    }

    onBubbleTextChanged: {
        if (bubbleText.length > 0) {
            bubbleHideTimer.restart()
            cuteMouth.requestPaint()
        }
    }

    onSpeechTextChanged: {
        if (speechText.length > 0) {
            bubbleHideTimer.restart()
            cuteMouth.requestPaint()
        }
    }
}
