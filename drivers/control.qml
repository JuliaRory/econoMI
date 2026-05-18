import QtQuick 2.5
import Resonance 3.0
import QtQuick.Controls 1.4

ApplicationWindow {
    id: root
    
    Component.onCompleted: {
        ResonanceApp.setServiceName('Resonance-control')    // сервис для для контроля резонансовых модулей
    }

    Parameters {
        Stream {
            id: control_message     
            name: 'controlSignal'                           // имя потока
            label: 'controlSignal' 
        }
        String {
            id: service_name
            name: "service name"
            label: "service name"
            value: "nvx136"
        }
        String {
            id: stream_name
            name: "stream_name"
            label: "stream_name"
            value: "eeg"
        }
        String {
            id: app_service_name
            name: "app_service_name"
            label: "app_service_name"
            value: "econoMI"
        }
        String {
            id: rec_filename
            name: "rec_filename"
            label: "rec_filename"
            value: "C:\\Users\\hodor\\Documents\\lab-MSU\\Works\\2025.10_econoMI\\econoMI_ui\\data\\rec-$$$.h5"
        }


    }

    MessageReceiver {  
        id: controlSignal_receiver 
		sourceInfo: control_message.desiredStream

        onMessage: {
            // message — это JSON вида:
            // {"service": "service_name", "type": "parameter", "parameter": "parameter_name", "value": "200"}
            // {"service": "service_name", "type": "command", "command": "command_name", "stream": "stream_name"}
            
            var msg = JSON.parse(text);

            let service = ResonanceApp.getService(msg.service)

            print(text)

            if (msg.type === "command") {
                if (msg.command == "!terminate") {service.sendTransition(msg.command)};
                
                if (msg.command == "start") {
                    service_name.value = msg.service || service_name.value;
                    stream_name.value = msg.stream || stream_name.value;
                    app_service_name.value = msg.app_service_name || app_service_name.value;
                    recorder.hdfFileName = msg.filename
                    recorder.start();
                    print("--- start the record --- ");
                    };

                if (msg.command == "stop") {
                    recorder.finish();
                    print("--- finish the record --- ");
                    };
                }

            if (msg.type == "parameter") {
                print("parameter"); 
                service.sendParameter(msg.parameter, msg.value);
            }

            if (msg.type == "check") {
                print("check");
                if (service) {print("YES");}
                else {print("NO");}

            }
            
        }
    }

    Recording {  // запускает qml
            id: recorder
            hdfFileName: rec_filename.value
            //eventStreamDiscovery: 'discover:///?stream=events&name=Stimulus%20Presentation'
			use_nvx: true
            service_name: service_name.value
            stream_name: stream_name.value
            app_service_name: app_service_name.value
			use_speed: false
		}
}
