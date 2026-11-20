/* OS XIII — diaporama pendant l'installation : chaque image remplit toute la zone (plus de bords blancs) */
import QtQuick 2.0;
import calamares.slideshow 1.0;
Presentation {
    id: presentation
    property var images: ["diapo1.png", "diapo2.png", "diapo3.png", "diapo4.png"]
    function nextSlide() { presentation.goToNextSlide(); }
    Timer { id: minuteur; interval: 7000; running: presentation.activatedInCalamares; repeat: true; onTriggered: nextSlide() }
    Rectangle { anchors.fill: parent; color: "#141210"; z: -2 }
    Image {
        anchors.fill: parent; z: -1
        fillMode: Image.PreserveAspectCrop; smooth: true
        source: presentation.images[Math.max(0, presentation.currentSlide) % presentation.images.length]
    }
    Slide { }
    Slide { }
    Slide { }
    Slide { }
    function onActivate() { presentation.currentSlide = 0; }
    function onLeave() { }
}
