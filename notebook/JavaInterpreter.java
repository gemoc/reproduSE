import java.util.List;
import java.util.Scanner;
import jdk.jshell.JShell;
import jdk.jshell.Snippet;
import jdk.jshell.SnippetEvent;
import jdk.jshell.SourceCodeAnalysis;

public class JavaInterpreter {
    public static void main(String args[]) {
        JShell jshell = JShell.create();
        
        Scanner scanner = new Scanner(System.in);
        StringBuilder lines = new StringBuilder();
        while (scanner.hasNextLine()) {
            lines.append(scanner.nextLine()).append('\n');
        }
        
        String remainingLines = lines.toString();
        SourceCodeAnalysis.CompletionInfo completionInfo;
        boolean done = false;
        while (!done) {
            List<SnippetEvent> events = null;
            completionInfo = jshell.sourceCodeAnalysis().analyzeCompletion(remainingLines);
            switch (completionInfo.completeness()) {
                case COMPLETE:
                    events = jshell.eval(completionInfo.source());
                    remainingLines = completionInfo.remaining();
                    break;
                    
                case COMPLETE_WITH_SEMI:
                    events = jshell.eval(completionInfo.source() + ';');
                    remainingLines = completionInfo.remaining();
                    break;
                    
                case EMPTY:
                    done = true;
                    break;
                
                default:
                    System.err.println(completionInfo.completeness());
                    done = true;
            }        
            if (events != null) {
                for (SnippetEvent event : events) {
                    if (event.status() != Snippet.Status.VALID) {
                        System.err.println(event);
                    }
                }
            }
        }
    }
}